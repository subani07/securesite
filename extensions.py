from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
bcrypt = Bcrypt()
jwt = JWTManager()
csrf = CSRFProtect()
mail = Mail()
oauth = OAuth()
