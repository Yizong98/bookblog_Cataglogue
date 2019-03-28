from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Book, Base, MenuItem, Author, User

engine = create_engine('sqlite:///bookscatalogue.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()


# Create dummy user
User1 = User(name="STOOPID", email="sixnine@ucsd.com",
             picture='https://i.ytimg.com/vi/JSpMHjCe_CM/maxresdefault.jpg')
session.add(User1)
session.commit()
# Book for Philosophy
category1 = Book(user_id=1, name="About Philosophy")

session.add(category1)
session.commit()

author1 = Author(name="Jordan Peterson")

session.add(author1)
session.commit()


menuItem1 = MenuItem(user_id=1, name="12 Rules of Life",
                     description="When JP teaches how to live, \
you just listen.",
                     price="12.99", book=category1,
                     author=author1, author_name="Jordan Peterson")

session.add(menuItem1)
session.commit()

author2 = Author(name="Plato")

session.add(author2)
session.commit()

menuItem2 = MenuItem(user_id=1, name="22 Rules of Life",
                     description="When ZONG teaches how to live, \
you just listen.",
                     price="12.99", book=category1,
                     author=author2, author_name='Plato')

session.add(menuItem2)
session.commit()

category1 = Book(user_id=1, name="About Business")

session.add(category1)
session.commit()

author1 = Author(name="Peter Thiel")

session.add(author1)
session.commit()


menuItem1 = MenuItem(user_id=1, name="Zero to One",
                     description="When the GOAT investor speaks, \
you just listen.",
                     price="12.99", book=category1,
                     author=author1, author_name="Peter Thiel")

session.add(menuItem1)
session.commit()

author2 = Author(name="Sheryl Sandberg")

session.add(author2)
session.commit()

menuItem2 = MenuItem(user_id=1, name="Lean In: Women, Work, \
and the Will to Lead",
                     description="When FB COO teaches how to lead, \
you just listen.",
                     price="12.99", book=category1,
                     author=author2, author_name='Sheryl Sandberg')

session.add(menuItem2)
session.commit()
print "added menu items!"
