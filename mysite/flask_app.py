import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template
from packingapp.app import packing_bp
from liftingapp.app import lifting_bp

app = Flask(__name__, template_folder='templates')

app.register_blueprint(packing_bp, url_prefix='/packing')
app.register_blueprint(lifting_bp, url_prefix='/lifting')

@app.route('/')
def landing():
    return render_template('landing.html')

if __name__ == '__main__':
    app.run(debug=True)
