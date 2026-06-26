from flask import Flask, render_template , request 
from pymongo import MongoClient
import os 
import bcrypt
import random
import string
from datetime import datetime, timedelta
from flask import send_file
from flask import redirect
from cryptography.fernet import Fernet
import tempfile
from flask import make_response
import uuid
app = Flask(__name__)


# MongoDB Connection
client = MongoClient(
    os.environ.get("MONGODB_URI")
)
db = client["sharesafe"]
files_collection = db["files"]

# Fernet Encryption Key
FERNET_KEY = b"JMF7Xr23K4B2-INov_OweWMDahw-RIHnUuWBMVi_i2U="

cipher = Fernet(FERNET_KEY)

# token genration 
def generate_token():
    chars = string.ascii_uppercase + string.digit
    return ''.join(random.choices(chars, k=7))

# password genration 
def generate_password():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))

# Generate Password

def get_owner_id():
    owner_id = request.cookies.get("owner_id")

    if not owner_id:
        owner_id = str(uuid.uuid4())

    return owner_id
# Home Page
@app.route("/")
def index ():
    return render_template("home.html")
@app.route("/home")
def home():
    return render_template("home.html")


# Share Page
@app.route("/share")
def share():
    return render_template("share.html")


# Success Page
@app.route("/success")
def success():
    return render_template("success.html")


# Receive Page
@app.route("/receive")
def receive():
    return render_template("receive.html")


# Verify Page
@app.route("/verify")
def verify():
    return render_template("verify.html")


# Download Page
@app.route("/download")
def download():
    return render_template("download.html")


# Invalid Password Page
@app.route("/invalid")
def invalid():
    return render_template("invalid.html")


# Expired Page
@app.route("/expired")
def expired():
    return render_template("expired.html")


# My Files Page



# Details Page
@app.route("/details/<token>")
def details(token):

    file_data = files_collection.find_one({
        "token": token
    })

    if not file_data:
        return render_template("invalid.html")

    if datetime.now() > file_data["expiry_time"]:

        files_collection.update_one(
            {"token": token},
            {"$set": {"status": "expired"}}
        )

        file_data["status"] = "expired"

    return render_template(
        "details.html",
        file=file_data
    )
# MongoDB Test
@app.route("/testdb")
def testdb():

    try:
        count = files_collection.count_documents({})
        return f"MongoDB Connected! Files: {count}"

    except Exception as e:
        return f"MongoDB Error: {e}"

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files["file"]
    expiry = request.form["expiry"]

    if file.filename == "":
        return "No File Selected"

    # Generate Token
    token = generate_token()

    # Generate Password
    password = generate_password()

    # Browser Owner ID
    owner_id = get_owner_id()

    # Hash Password
    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    # Read Original File
    file_bytes = file.read()

    # Encrypt File
    encrypted_data = cipher.encrypt(file_bytes)

    # Save Encrypted File
    filename = f"{token}.enc"
    filepath = os.path.join("uploads", filename)

    with open(filepath, "wb") as f:
        f.write(encrypted_data)

    # Expiry Time
    expiry_hours = int(expiry)
    expiry_time = datetime.now() + timedelta(hours=expiry_hours)

    # Save MongoDB
    file_data = {
        "owner_id": owner_id,
        "file_name": file.filename,
        "stored_file": filename,
        "filepath": filepath,
        "token": token,
        "password": hashed_password,
        "expiry_time": expiry_time,
        "created_at": datetime.now(),
        "download_count": 0,
        "status": "active"
    }

    files_collection.insert_one(file_data)

    secure_link = f"http://127.0.0.1:5000/download/{token}"

    response = make_response(render_template(
        "success.html",
        file_name=file.filename,
        token=token,
        secure_link=secure_link,
        generated_password=password,
        expiry_date=expiry_time,
        status="Active"
    ))

    response.set_cookie(
        "owner_id",
        owner_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="Lax"
    )

    return response

@app.route("/download/<token>")
def download_link(token):

    file_data = files_collection.find_one({
        "token": token
    })

    if not file_data:
        return render_template("invalid.html")

    if datetime.now() > file_data["expiry_time"]:

        files_collection.update_one(
            {"token": token},
            {"$set": {"status": "expired"}}
        )

        return render_template("expired.html")

    return render_template(
        "verify.html",
        token=token,
        file_name=file_data["file_name"]
    )


@app.route("/check-password", methods=["POST"])
def check_password():

    token = request.form["token"]
    password = request.form["password"]

    file_data = files_collection.find_one({
        "token": token
    })

    if not file_data:
        return render_template("invalid.html")

    if not bcrypt.checkpw(
    password.encode("utf-8"),
    file_data["password"].encode("utf-8")
):
     return render_template("invalid.html")

    # Expiry Check
    if datetime.now() > file_data["expiry_time"]:

        files_collection.update_one(
            {"token": token},
            {"$set": {"status": "expired"}}
        )

        return render_template("expired.html")

    return render_template(
        "download.html",
        file_name=file_data["file_name"],
        token=token,
        status=file_data["status"],
        expiry_date=file_data["expiry_time"],
        download_count=file_data["download_count"]
    )

@app.route("/open-link")
def open_link():

    share_link = request.args.get("share_link")

    if not share_link:
        return render_template("invalid.html")

    try:
        token = share_link.split("/")[-1]

        file_data = files_collection.find_one({
            "token": token
        })

        if not file_data:
            return render_template("invalid.html")

        return render_template(
            "verify.html",
            token=token,
            file_name=file_data["file_name"]
        )

    except:
        return render_template("invalid.html")
@app.route("/download-file/<token>")
def download_file(token):

    file_data = files_collection.find_one({
        "token": token
    })

    if not file_data:
        return render_template("invalid.html")

    filepath = file_data["filepath"]

    # Read Encrypted File
    with open(filepath, "rb") as f:
        encrypted_data = f.read()

    # Decrypt File
    decrypted_data = cipher.decrypt(encrypted_data)

    # Create Temporary File
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix="_" + file_data["file_name"]
    )

    temp_file.write(decrypted_data)
    temp_file.close()

    # Download Counter +1
    files_collection.update_one(
        {"token": token},
        {"$inc": {"download_count": 1}}
    )

    return send_file(
        temp_file.name,
        as_attachment=True,
        download_name=file_data["file_name"]
    )



@app.route("/delete/<token>")
def delete_file(token):

    file_data = files_collection.find_one({
        "token": token
    })

    if not file_data:
        return render_template("invalid.html")

    filepath = file_data.get("filepath")

    if filepath and os.path.exists(filepath):
        os.remove(filepath)

    files_collection.delete_one({
        "token": token
    })

    return redirect("/myfiles")

@app.route("/myfiles")
def myfiles():

    # Current browser owner
    owner_id = request.cookies.get("owner_id")

    # Show only this user's files
    files = list(files_collection.find({
        "owner_id": owner_id
    }))

    now = datetime.now()

    for file in files:

        if now > file["expiry_time"]:

            files_collection.update_one(
                {"token": file["token"]},
                {"$set": {"status": "expired"}}
            )

            file["status"] = "expired"

    return render_template(
        "myfiles.html",
        files=files
    )
if __name__ == "__main__":
    app.run(debug=True)