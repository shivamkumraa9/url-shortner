from flask import Flask,render_template,redirect,request,jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

from email.message import EmailMessage 
from functools import wraps
import smtplib
import binascii
import os



##################################################### Settings ####################################################


EMAIL = os.environ['EMAIL']
PASSWORD = os.environ['PASSWORD']
SITE = "https://iurl-shortner.herokuapp.com/"


app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tmp/test.db'
db = SQLAlchemy(app)



###################################################### DB Models #################################################


class User(db.Model):
	id = db.Column(db.Integer,primary_key = True)
	email = db.Column(db.String(30),unique = True)
	token = db.Column(db.String(40),unique = True)
	urls = db.relationship('Url',backref = 'user')

	def __repr__(self):
		return self.email

class Url(db.Model):
	id = db.Column(db.Integer,primary_key = True)
	original_url = db.Column(db.String(100))
	shoten_url_code = db.Column(db.String(6))
	shoten_url = db.Column(db.String(20))
	hits = db.Column(db.Integer)
	user_id = db.Column(db.Integer,db.ForeignKey('user.id'))



#################################################### VIEW DECORATORS #################################################

def token_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
    	token = request.form.get("token")
    	if token:
    		user = User.query.filter_by(token = token).first()
    		if user:
    			return f(user,*args, **kwargs)
    		else:
    			return jsonify({"error":"invalid token"}),404
    	return jsonify({"error":"Token Not Found"}),404
    return decorated_function



def url_auth(f):
    @wraps(f)
    def decorated_function(user,*args, **kwargs):
    	url = request.form.get("url")
    	if url:
    		return f(user,url,*args, **kwargs)
    	return jsonify({"error":"Url not found"}),404
    return decorated_function


def url_db_auth(f):
    @wraps(f)
    def decorated_function(user,url,*args, **kwargs):
    	url = Url.query.filter_by(user = user,shoten_url = url).first()
    	if not url:
                return jsonify({"error":"Invalid Url"}),404
    	return f(url,*args, **kwargs)
    return decorated_function


########################################################### HELPER FUNCTIONS ##########################################


def get_token(l):
	return binascii.hexlify(os.urandom(l)).decode()


def send_mail(token,reciever):
	msg = EmailMessage()
	msg['Subject'] = "Url Shortner Token"
	msg['From'] = EMAIL
	msg['To'] = [reciever]
	message = f"Your Token : {token}"
	msg.set_content(message)

	with smtplib.SMTP_SSL("smtp.gmail.com",465) as smtp:
		smtp.login(EMAIL,PASSWORD)
		smtp.send_message(msg)

def get_url_data(url):
	return {"original":url.original_url,"code":url.shoten_url_code,"short":url.shoten_url,"hits":url.hits}


###################################################### VIEWS #########################################################


@app.route("/",methods=['GET'])
def index():
	return render_template("index.html")


@app.route("/<string:code>/",methods=['GET'])
def redirect_user(code):
	url = Url.query.filter_by(shoten_url_code = code).first_or_404()
	url.hits += 1
	db.session.commit()
	return redirect(url.original_url)

@app.route("/api/docs/",methods=['GET'])
def docs():
	return render_template("docs.html")


@app.route("/api/user/generate-token/",methods = ['POST'])
def generate_token():
	email = request.form.get("email")
	if email:
		user = User.query.filter_by(email = email).first()
		if not user:
			user = User(email = email,token = get_token(20))
			db.session.add(user)
			db.session.commit()
		send_mail(user.token,user.email)
		return jsonify({"status":" token sent to email"})
	return jsonify({"error":"Email not found"}),404


@app.route("/api/user/change-token/",methods = ['PUT'])
@token_auth
def change_token(user):
	new_token = get_token(20)
	user.token = new_token
	db.session.commit()
	send_mail(new_token,user.email)
	return jsonify({"status":" token sent to email"})


@app.route("/api/user/delete-account/",methods = ['DELETE'])
@token_auth
def delete_account(user):
	for i in Url.query.filter_by(user = user):
		db.session.delete(i)
	db.session.delete(user)
	db.session.commit()
	return jsonify({"status":"account deleted"})



@app.route("/api/url/stats/",methods = ["GET"])
@token_auth
@url_auth
@url_db_auth
def stats_single(url):
	return jsonify(get_url_data(url))


@app.route("/api/url/stats/all/",methods = ["GET"])
@token_auth
def stats_all(user):
	data = []
	for i in Url.query.filter_by(user = user):
		data.append(get_url_data(i))
	return jsonify(data)


@app.route("/api/url/generate-url/",methods = ["POST"])
@token_auth
@url_auth
def generate_url(user,url):
	t = get_token(3)
	url = Url(original_url = url,shoten_url_code = t , shoten_url = SITE+t+'/',user = user,hits= 0)
	db.session.add(url)
	db.session.commit()
	return jsonify(get_url_data(url))


@app.route("/api/url/delete-url/",methods = ["DELETE"])
@token_auth
@url_auth
@url_db_auth
def delete_url(url):
	db.session.delete(url)
	db.session.commit()
	return jsonify({"status":"deleted successfully"})


@app.route("/api/url/delete-url/all/",methods = ["DELETE"])
@token_auth
def delete_url_all(user):
	for i in Url.query.filter_by(user = user):
		db.session.delete(i)
	db.session.commit()
	return jsonify({"status":"deleted successfully"})



if __name__ == "__main__":
	app.run(debug = True)
