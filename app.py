import io
import os
import dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import pandas as pd
from chat2plot import chat2plot
from langchain_community.chat_models import ChatOpenAI
import plotly.io as pio
from plotly.io import to_image
from werkzeug.utils import secure_filename
import re


dotenv.load_dotenv()    
api = os.getenv('api_key')
 
if api is not None:
    os.environ["OPENAI_API_KEY"] = api
else:
    # Handle  api
    print("API key is not available.")
 

app = Flask(__name__)

app.secret_key = 'your_secret_key_here'

# Global DataFrame
df = pd.DataFrame()
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'txt', 'csv', 'xls', 'xlsx'}

USERS = {
    'admin@expleo.com': 'expleo@1234',
    'Ei54857@expleo.com': 'expleo@12345'
 
}

@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the username and password are correct
        if USERS.get(username) == password:
            session['username'] = username
            return redirect(url_for('upload'))

        return render_template('login.html', error='Incorrect Username or Password')

    return render_template('login.html')
 
def clean_column_name(name):
    # Remove all symbols and spaces using regex
    cleaned_name = re.sub(r'[^A-Za-z0-9]+', '', name)
    return cleaned_name
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global df
    print('inside upload Function')

    if 'username' not in session:
        print('inside if statement for username')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('upload.html', error_message="No file part")
        uploaded_file = request.files['file']

        if uploaded_file.filename == '':
            return render_template('upload.html', error_message="No selected file")

        if allowed_file(uploaded_file.filename):
            try:
                if uploaded_file.filename.lower().endswith('.csv'):
                    print('inside csv read')
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.filename.lower().endswith(('.xls', '.xlsx')):
                    print('inside xls read')
                    df = pd.read_excel(uploaded_file)
                else:
                    return render_template('upload.html', error_message="Unsupported file type")
                print('Dataframe head')
                print(df.head())  
                
                return redirect(url_for('index'))

            except Exception as e:
                return render_template('upload.html', error_message=f"An error occurred while reading the file: {str(e)}")
        else:
            return render_template('upload.html', error_message="Allowed file types are csv, xls, xlsx")

    return render_template('upload.html')

@app.route('/index', methods=['GET', 'POST'])
def index():
    global df
    print('inside index')
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        filename = session.get('uploaded_filename')
        
        if not filename:
            print('No file has been uploaded.')
            return render_template('index.html', error_message="No file has been uploaded.")

        try:
            print('Data head')
            print(df.head())
        except Exception as e:
            return render_template('index.html', error_message=f"An error occurred while reading the file: {str(e)}")

        query = request.form['query']

        try:
            full_query = (
                f"As an expert data analyst, please ensure that you handle data type conversions and error handling appropriately. "
                f"Visualize the following dataset using distinct colors for clarity. Here is a preview of the data:\n\n"
                f"{df.head(5).to_string()}\n\n"
                f"Based on this data, address the following query: '{query}'. "
                "Generate an accurate visualization, provide a comprehensive explanation, and offer any significant insights or trends. "
                "Ensure to handle any data inconsistencies or conversion issues you encounter and dont."
            )

            c2p = chat2plot(df.copy(), chat=ChatOpenAI(model='gpt-3.5-turbo'))
            result = c2p(full_query)
            graph_html = pio.to_html(result.figure, full_html=False)
            explanation = result.explanation
            
            return render_template('index.html', graph_html=graph_html, explanation=explanation, query=query)
        except Exception as e:
            error_message = str(e)
            return render_template('index.html', error_message=error_message)
    else:
        return render_template('index.html')
    
dashboard_plots = []
@app.route('/save_to_dashboard', methods=['POST'])
def save_to_dashboard():
    if 'username' not in session:
        return jsonify({'error': 'User not logged in'}), 401
    
    data = request.get_json()
    img_uri = data.get('img_uri')
    prompt = data.get('prompt')
 
    if img_uri and prompt:
        # Save the plot to the dashboard
        dashboard_plots.append({'prompt': prompt, 'img_uri': img_uri})
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid data'}), 400
 
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
                        
    return render_template('dashboard.html', dashboard_plots=dashboard_plots)

if __name__ == '__main__':
    app.run(debug=True)
