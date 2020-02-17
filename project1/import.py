import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = create_engine('postgres://xvfqwrzgppnzdg:0f69793a9e538a174a5c3e5c3baf3e9c701ceb3c6b27c151d7715e39a0ee9376@ec2-3-230-106-126.compute-1.amazonaws.com:5432/dc0aako6mb7lag')
db = scoped_session(sessionmaker(bind=engine))


def main():
    f = open("books.csv", "r")
    reader = csv.reader(f)
    next(reader)
    for isbn, title, author, year in reader:
        db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
               {"isbn": isbn, "title": title, "author": author, "year": year})
        db.commit()
        print(f"Added book with ISBN: {isbn} Title: {title}  Author: {author}  Year: {year}")


if __name__ == '__main__':
    main()