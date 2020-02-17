import os
import requests

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Check for environment variable even though the create_engine is using the database url because I'm not very bright
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine('postgres://xvfqwrzgppnzdg:0f69793a9e538a174a5c3e5c3baf3e9c701ceb3c6b27c151d7715e39a0ee9376@ec2-3-230-106-126.compute-1.amazonaws.com:5432/dc0aako6mb7lag')

db = scoped_session(sessionmaker(bind=engine))


# Homepage
@app.route("/")
def index():
    status = "Loggedout"
    try:
        username=session["username"]
        status=""
    except KeyError:
        username=""
    return render_template("index.html", work="Login", status=status, username=username)


# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    # Request rom /register
    if request.method == "POST":
        username = request.form.get("username")
        # Checking if the user is registered
        if db.execute("SELECT id FROM userbase WHERE username= :username", {"username": username}).fetchone() is not None:
            return render_template("login.html", work="Login",
                                   error_message="The user has already registered. Please Login.")
        password = request.form.get("Password")
        db.execute("INSERT INTO userbase (username, password) VALUES (:username, :password)",
                   {"username": username, "password": generate_password_hash(password)})
        db.commit()
        return render_template("login.html", work="Login", message="Success")

    return render_template("login.html", work="Login")


# Logout for the website
@app.route("/logout")
def logout():
    try:
        session.pop("username")
    except KeyError:
        return render_template("login.html", work="Login", error_message="Please Login First")
    return render_template("index.html", work="Login", status="Loggedout")


# Register Page
@app.route("/register")
def register():
    return render_template("login.html", work="Register")


# Comes after logging in
@app.route("/search", methods=["GET", "POST"])
def search():
    # Request from /login to log a user in
    if request.method == "POST":
        # Checking if the user is present, if not present show error message and redirect to /register
        username = request.form.get("username")
        user = db.execute("SELECT id, password FROM userbase WHERE username= :username", {"username": username}).fetchone()
        if user is None:
            return render_template("login.html", error_message="The user hasn't been registered. Please register.",
                                   work="Register")

        password = request.form.get("Password")
        if not check_password_hash(user.password, password):
            return render_template("login.html", error_message="Your password doesn't match to that of " + username +
                                                               ". Please try again.", work="Login")
        session["username"] = username
        session["user_id"] = user.id
    if request.method == "GET" and "username" not in session:
        return render_template("login.html", error_message="Please Login First", work="Login")
    return render_template("search.html", username=username)


# Page to show books as per search result
@app.route("/booklist", methods=["POST"])
def booklist():
    if "username" not in session:
        return render_template("login.html", error_message="Please Login First", work="Login")

    book_column = request.form.get("book_column")
    query = request.form.get("query")

    if book_column == "year":
        book_list = db.execute("SELECT * FROM books WHERE year = :query", {"query": query}).fetchall()
    else:
        book_list = db.execute("SELECT * FROM books WHERE UPPER(" + book_column + ") LIKE :query ORDER BY title",
                               {"query": "%" + query.upper() + "%"}).fetchall()

    if len(book_list):
        return render_template("booklist.html", book_list=book_list, username=session["username"])

    elif book_column != "year":
        error_message = "We couldn't find the books you searched for."
        if not len(book_list):
            return render_template("error.html", error_message=error_message)
        message = "You might be searching for:"
        return render_template("booklist.html", error_message=error_message, book_list=book_list, message=message,
                               username=session["username"])
    else:
        return render_template("error.html", error_message="We didn't find any book with the year you typed."
                                                          " Please check for errors and try again.")


# Detail about book that matches id
@app.route("/detail/<int:book_id>", methods=["GET", "POST"])
def detail(book_id):
    if "username" not in session:
        return render_template("login.html", error_message="Please Login First", work="Login")

    book = db.execute("SELECT * FROM books WHERE id = :book_id", {"book_id": book_id}).fetchone()
    if book is None:
        return render_template("error.html", error_message="We got an invalid book id"
                                                           ". Please check for the errors and try again.")

    # Summiting review.
    if request.method == "POST":
        user_id = session["user_id"]
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        if db.execute("SELECT id FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                      {"user_id": user_id, "book_id": book_id}).fetchone() is None:
            db.execute(
                "INSERT INTO reviews (user_id, book_id, rating, comment) VALUES (:user_id, :book_id, :rating, :comment)",
                {"book_id": book.id, "user_id": user_id, "rating": rating, "comment": comment})
        else:
            db.execute(
                "UPDATE reviews SET comment = :comment, rating = :rating WHERE user_id = :user_id AND book_id = :book_id",
                {"comment": comment, "rating": rating, "user_id": user_id, "book_id": book_id})
        db.commit()

    # Processing json from goodreads
    res = requests.get("https://www.goodreads.com/book/review_counts.json",
                       params={"key": "ciOVC4V8WZ9EtWjYCdxRUg", "isbns": book.isbn}).json()["books"][0]

    ratings_count = res["ratings_count"]
    average_rating = res["average_rating"]
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
    userbase = []
    for review in reviews:
        username = db.execute("SELECT username FROM userbase WHERE id = :user_id", {"user_id": review.user_id}).fetchone().username
        userbase.append((username, review))

    return render_template("detail.html", book=book, userbase=userbase,
                           ratings_count=ratings_count, average_rating=average_rating, username=session["username"])


# Page for the website's API
@app.route("/api/<ISBN>", methods=["GET"])
def api(ISBN):
    book = db.execute("SELECT * FROM books WHERE isbn = :ISBN", {"ISBN": ISBN}).fetchone()
    if book is None:
        return render_template("error.html", error_message="We got an invalid ISBN. "
                                                           "Please check for the errors and try again.")
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id": book.id}).fetchall()
    count = 0
    rating = 0
    for review in reviews:
        count += 1
        rating += review.rating
    if count:
        average_rating = rating / count
    else:
        average_rating = 0

    return jsonify(
        title=book.title,
        author=book.author,
        year=book.year,
        isbn=book.isbn,
        review_count=count,
        average_score=average_rating
    )


if __name__ == "__main__":
    app.run(debug=True)
