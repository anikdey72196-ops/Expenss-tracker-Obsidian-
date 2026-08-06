from flask_wtf import FlaskForm
from wtforms import StringField,PasswordField,SubmitField
from wtforms.validators import DataRequired,Email,Length

class RegistrationForm(FlaskForm):
    username=StringField('username',validators=[
        DataRequired(),
        Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
    ])
    password=PasswordField('password',validators=[
        DataRequired(),
        Length(min=8, max=72, message="Password must be between 8 and 72 characters.")
    ])
    submit=SubmitField('Register')

class LoginForm(FlaskForm):
    username=StringField('username',validators=[DataRequired(), Length(max=80)])
    password=PasswordField('password',validators=[DataRequired(), Length(max=72)])
    submit=SubmitField('Sign In')
