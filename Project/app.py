from flask import Flask
server = Flask(__name__)

@server.route("/")
def hello():
    return "<h1 style='color:blue'>Hello There baby!</h1>"

if __name__ == "__main__":
    server.run(host='0.0.0.0')