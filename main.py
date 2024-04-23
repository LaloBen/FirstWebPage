from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, URLField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
import datetime as dt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
# Import your forms from the forms.py
from forms import CreatePostForm
from forms import RegisterForm
from forms import LoginForm
from forms import CommentForm
# To authorize routes only to admin
from functools import wraps
from flask import abort
# To apply basic relationship patterns
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
# For environment variables
import os
from dotenv import load_dotenv

load_dotenv()



app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_KEY')
Bootstrap5(app)
CKEditor(app)

class MyForm(FlaskForm):
    title = StringField(label='Blog Post Tilte',validators=[DataRequired()])
    subtitle = StringField(label='Subtitle',validators=[DataRequired()])
    author = StringField(label='Author Name',validators=[DataRequired()])
    img_url = URLField(label='Image URL',validators=[DataRequired(),URL()])
    body = CKEditorField(label='Body',validators=[DataRequired()])
    submit = SubmitField(label='Submit Post')

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI')
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLE
class BlogPost(db.Model):
    __tablename__ = 'blog_posts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer,db.ForeignKey('users.id'))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship('User', back_populates='posts')
    #***************Parent Relationship*************#
    comment = relationship('Comments',back_populates='parent_post')
    

# TODO: Create a User table for all your registered users. 
class User(UserMixin,db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(250),unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
     #This will act like a List of BlogPost objects attached to each User. 
    #The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    #*******Add parent relationship*******#
    #"comment_author" refers to the comment_author property in the Comment class.
    comments = relationship('Comments', back_populates='comment_author')

# Create Comments table
class Comments(db.Model):
    __tablename__ = 'post_comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    #*******Add child relationship*******#
    #"users.id" The users refers to the tablename of the Users class.
    #"comments" refers to the comments property in the User class.
    author_id: Mapped[int] = mapped_column(Integer,db.ForeignKey('users.id'))
    comment_author = relationship('User', back_populates='comments')
    #***************Child Relationship*************#
    post_id: Mapped[int] = mapped_column(Integer,db.ForeignKey('blog_posts.id'))
    parent_post = relationship('BlogPost',back_populates='comment')


with app.app_context():
    db.create_all()

# ADD LOG IN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

# Create a user loader callback
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User,user_id)

# Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1 :
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=['GET','POST'])
def register():
    form = RegisterForm()
    u_email = form.email.data
    u_name = form.name.data
    u_password = form.password.data
    result =  db.session.execute(db.select(User).where(User.email == u_email))
    user = result.scalar()
    if user:
        flash("You've already signed up with that email, log in instead!")
        return redirect(url_for('login'))
    else:
        if form.validate_on_submit():
            s_password = generate_password_hash(u_password,method='pbkdf2:sha256',salt_length=8)
            user_to_add = User(
                    name = u_name,
                    email = u_email,
                    password = s_password
                )
            db.session.add(user_to_add)
            db.session.commit()
            #once registered, log in the user and redirect it to home page
            login_user(user_to_add)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html",form=form,logged_in=current_user.is_authenticated)

# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET','POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()

        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
    
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)
    

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    # TODO: Query the database for all the posts. Convert the data to a python list.
    result = db.session.execute(db.select(BlogPost).order_by(BlogPost.id.asc()))
    post_list = result.scalars().all()
    # post_list_2 = [i.__dict__ for i in post_list]
    return render_template("index.html", all_posts=post_list, logged_in=current_user.is_authenticated, current_user=current_user)

# TODO: Add a route so that you can click on individual posts.
@app.route('/posts/blog_<int:post_id>',methods=['GET','POST'])
def show_post(post_id):
    # TODO: Retrieve a BlogPost from the database based on the post_id
    requested_post = db.get_or_404(BlogPost,post_id)
    form = CommentForm()
    # Only allow logged-in users to comment on posts
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Please login first or register before you comment')
            return redirect(url_for('login'))
        new_comment = Comments(
            comment = form.comment_text.data,
            comment_author = current_user,
            parent_post = requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    result = db.session.execute(db.select(Comments))
    comment_list = result.scalars().all()

    return render_template("post.html", post=requested_post,current_user=current_user,logged_in=current_user.is_authenticated,form=form,all_comments=comment_list)


# TODO: add_new_post() to create a new blog post
@app.route('/new_post',methods=['GET','POST'])
# Use the admin-only decorator
@admin_only
def add_post():
    form=MyForm()
    blog_title = form.title.data
    blog_subtitle = form.subtitle.data
    blog_author = form.author.data
    blog_img_url = form.img_url.data 
    blog_body = form.body.data
    blog_date = dt.datetime.now().strftime("%B %d, %Y") 
    if form.validate_on_submit():
        new_blogpost = BlogPost(
                        title = blog_title,
                        subtitle = blog_subtitle,
                        date = blog_date,
                        body = blog_body,
                        author = current_user,
                        # author = blog_author,
                        img_url = blog_img_url
                    )
        db.session.add(new_blogpost)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    return render_template('make-post.html',form=form,page='add',logged_in=current_user.is_authenticated,current_user=current_user)

# TODO: edit_post() to change an existing blog post
@app.route('/edit_post/<int:post_id>',methods=['GET','POST'])
# Use the admin-only decorator
@admin_only
def edit_post(post_id):
    blog_date = dt.datetime.now().strftime("%B %d, %Y")
    requested_post = db.get_or_404(BlogPost,post_id)
    form = MyForm(
        #to autofill info with the last update
        title = requested_post.title,
        subtitle = requested_post.subtitle,
        date = requested_post.date,
        body = requested_post.body,
        author = requested_post.author,
        img_url = requested_post.img_url
    )
    if form.validate_on_submit():
        requested_post.title = form.title.data
        requested_post.subtitle = form.subtitle.data
        # we do not want to replace the creation date
        # requested_post.date = blog_date
        requested_post.body = form.body.data
        requested_post.author = form.author.data
        requested_post.img_url = form.img_url.data
        db.session.commit()
        return redirect(url_for('show_post',post_id=requested_post.id))
    return render_template('make-post.html',form=form,post=requested_post,page='edit',logged_in=current_user.is_authenticated)

# TODO: delete_post() to remove a blog post from the database
@app.route('/delete/<int:post_id>')
# Use the admin-only decorator
@admin_only
#post_id is passed from index.html as a url parameter
def delete_page(post_id):
    post_to_delete = db.get_or_404(BlogPost,post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))
# Below is the code from previous lessons. No changes needed.
@app.route("/about")
def about():
    return render_template("about.html",logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html",logged_in=current_user.is_authenticated)


if __name__ == "__main__":
    app.run(debug=False)
