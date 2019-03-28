import requests
from flask import make_response
import json
import httplib2
from oauth2client.client import FlowExchangeError
from oauth2client.client import flow_from_clientsecrets
import string
import random
from flask import session as login_session
from database_setup import Book, Base, MenuItem, Author, User
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, asc
from flask import Flask, render_template, request, redirect,\
    jsonify, url_for, flash

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Books Recommendation Application"

# Connect to Database and create database session
engine = create_engine('sqlite:///bookscatalogue.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token


@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print "access token received %s " % access_token

    # Use token to get user info from API
    userinfo_url = "https://graph.facebook.com/me"

    url = '%s?access_token=%s&fields=name,id,email,picture' % (
        userinfo_url, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result
    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data["name"]
    login_session['email'] = data["email"]
    login_session['facebook_id'] = data["id"]

    # The token must be stored in the login_session in order to properly logout
    login_session['access_token'] = access_token

    # Get user picture
    login_session['picture'] = data["picture"]["data"]["url"]

    # see if user exists
    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    # create display output
    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px\
;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash("Now logged in as %s" % login_session['username'])
    return output


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']
    # The access token must me included to successfully logout
    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' % (
        facebook_id, access_token)
    h = httplib2.Http()
    print("AFTER     ", login_session['username'])
    result = h.request(url, 'DELETE')[1]
    return "you have been logged out"


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        print("WTF")
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is \
        	already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;\
-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
        % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    # When valid status, make response
    if result['status'] == '200':
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Show all categories


@app.route('/')
@app.route('/book/')
def showBooks():
    books = session.query(Book).order_by(asc(Book.name))
    menuitems = session.query(MenuItem).order_by(asc(MenuItem.author_name))
    names = set(item.author_name for item in menuitems)
    if 'username' not in login_session:
        return render_template('publicbooks.html', books=books, items=names)
    else:
        return render_template('books.html', books=books, items=names)
# Create a new Book


@app.route('/book/new/', methods=['GET', 'POST'])
def newBook():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        # When post, add new book
        newBook = Book(name=request.form['name'],
                       user_id=login_session['user_id'])
        session.add(newBook)
        flash('New Book %s Successfully Created' % newBook.name)
        session.commit()
        return redirect(url_for('showBooks'))
    else:
        return render_template('newBook.html')
# Edit a Book


@app.route('/book/<int:book_id>/edit/', methods=['GET', 'POST'])
def editBook(book_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedBook = session.query(Book).filter_by(id=book_id).one()
    # if id doesnt match, disokay alert
    if editedBook.user_id != login_session['user_id']:
        return "<script>function myFunction() \
        {alert('You are not authorized to edit this book.\
 Please create your own book in order to edit.');}\
        </script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name']:
            editedBook.name = request.form['name']
            flash('Book Successfully Edited %s' % editedBook.name)
            return redirect(url_for('showBooks'))
    else:
        return render_template('editBook.html', book=editedBook)


# Delete a Book
@app.route('/book/<int:book_id>/delete/', methods=['GET', 'POST'])
def deleteBook(book_id):
    if 'username' not in login_session:
        return redirect('/login')
    bookToDelete = session.query(Book).filter_by(id=book_id).one()
    print(bookToDelete.user_id)
    # if id doesnt match, disokay alert
    if bookToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() \
        {alert('You are not authorized to delete this book!\
 Please create your own book in order to delete.');}\
        </script><body onload='myFunction()'>"
    # see if post request
    if request.method == 'POST':
        session.delete(bookToDelete)
        session.query(MenuItem).filter_by(book_id=bookToDelete.id).delete()
        flash('%s Successfully Deleted' % bookToDelete.name)
        session.commit()
        return redirect(url_for('showBooks', book_id=book_id))
    else:
        # if it is Get, go to the delete page
        return render_template('deleteBook.html', book=bookToDelete)

# Show a book menu


@app.route('/book/<int:book_id>/')
@app.route('/book/<int:book_id>/menu/')
def showMenu(book_id):
    book = session.query(Book).filter_by(id=book_id).one()
    creator = getUserInfo(book.user_id)
    items = session.query(MenuItem).filter_by(book_id=book_id).all()
    print("HAHIDHSIDUHSDIU")
    print('username' not in login_session)
    print(login_session)
    if 'username' not in login_session or \
            creator.id != login_session['user_id']:
        return render_template('publicmenu.html',
                               items=items, book=book, creator=creator)
    else:
        return render_template('menu.html',
                               items=items, book=book, creator=creator)


# Create a new menu item
@app.route('/book/<int:book_id>/menu/new/', methods=['GET', 'POST'])
def newMenuItem(book_id):
    if 'username' not in login_session:
        return redirect('/login')
    book = session.query(Book).filter_by(id=book_id).one()
    # if id doesnt match, disokay alert
    if login_session['user_id'] != book.user_id:
        return "<script>function myFunction() \
        {alert('You are not authorized to add menu items\
to this book.\
 Please create your own book in order to add items.');\
        }</script><body onload='myFunction()'>"
    # add wgen post request
    if request.method == 'POST':
        newItem = MenuItem(name=request.form['name'],
                           description=request.form['description'],
                           price=request.form['price'],
                           author_name=request.form['author_name'],
                           book_id=book_id,
                           user_id=book.user_id)
        session.add(newItem)
        session.commit()
        flash('New Menu %s Item Successfully Created' % (newItem.name))
        return redirect(url_for('showMenu', book_id=book_id))
    else:
        return render_template('newmenuitem.html', book_id=book_id)

# Edit a menu item


@app.route('/book/<int:book_id>/menu/<int:menu_id>/edit',
           methods=['GET', 'POST'])
def editMenuItem(book_id, menu_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(MenuItem).filter_by(id=menu_id).one()
    book = session.query(Book).filter_by(id=book_id).one()
     # if id doesnt match, disokay alert
    if login_session['user_id'] != book.user_id:
        return "<script>function myFunction() \
        {alert('You are not authorized to edit menu \
items to this book.\
 Please create your own book in order to edit items.');\
        }</script><body onload='myFunction()'>"
    # delete wgen post request
    if request.method == 'POST':
        print(request.form)
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['author_name']:
            print("ITEM", editedItem.author_name)
            editedItem.author_name = request.form['author_name']
        session.add(editedItem)
        session.commit()
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', book_id=book_id))
    else:
        return render_template('editmenuitem.html',
                               book_id=book_id,
                               menu_id=menu_id, item=editedItem)


# Delete a menu item
@app.route('/book/<int:book_id>/menu/<int:menu_id>/delete',
           methods=['GET', 'POST'])
def deleteMenuItem(book_id, menu_id):
    if 'username' not in login_session:
        return redirect('/login')
    book = session.query(Book).filter_by(id=book_id).one()
    itemToDelete = session.query(MenuItem).filter_by(id=menu_id).one()
    # if id doesnt match, disokay alert
    if login_session['user_id'] != book.user_id:
        return "<script>function myFunction() \
        {alert('You are not authorized \
to delete menu items to this book. \
 Please create your own book in order to delete items.');\
        }</script><body onload='myFunction()'>"
    if request.method == 'POST':
        # delete wgen post request
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', book_id=book_id))
    else:
        return render_template('deleteMenuItem.html', item=itemToDelete)


# JSON APIs to view book Information
@app.route('/book/<int:book_id>/menu/JSON')
def BookMenuJSON(book_id):
    print(session.query(Book).filter_by(id=book_id).one())
    book = session.query(Book).filter_by(id=book_id).one()
    items = session.query(MenuItem).filter_by(book_id=book_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/book/<int:book_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(book_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id=menu_id).one()
    return jsonify(Menu_Item=Menu_Item.serialize)


@app.route('/book/JSON')
def BooksJSON():
    books = session.query(Book).all()
    return jsonify(books=[r.serialize for r in books])


def createUser(login_session):
    # Add user
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None
# Disconnect based on provider


@app.route('/disconnect')
def disconnect():
    # check whether user in session
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        # delete all session info when closerd
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash("You have successfully been logged out.")
        return redirect(url_for('showBooks'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showBooks'))


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)
