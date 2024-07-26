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


dotenv.load_dotenv()    
api = os.getenv('api_key')
 
if api is not None:
    os.environ["OPENAI_API_KEY"] = api
else:
    # Handle the case where api is None, perhaps by setting a default value or logging an error.
    print("API key is not available.")
 

app = Flask(__name__)

app.secret_key = 'your_secret_key_here'

# app.config['UPLOAD_FOLDER'] = 'uploads/'
# global df
df=[]
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'txt', 'csv', 'xls', 'xlsx'}

USERS = {
    'admin@expleo.com': 'expleo@1234'
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

def clear_tmp_folder(folder):
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                os.rmdir(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
            
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    global df
    print('innside upload')
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('upload.html', error_message="No file part")

        uploaded_file = request.files['file']

        if uploaded_file.filename == '':
            return render_template('upload.html', error_message="No selected file")

        if allowed_file(uploaded_file.filename):
            clear_tmp_folder('tmp')
            file_ext = uploaded_file.filename.rsplit('.', 1)[1].lower()
            filename = f"data_file.{file_ext}"
            file_path = os.path.join('tmp', filename)
            
            # filename = secure_filename(uploaded_file.filename)
            file_path = os.path.join('tmp', filename)

            try:
                uploaded_file.save(file_path)
                
                # Store the filename in the session
                session['uploaded_filename'] = filename
                df = read_file_from_tmp(filename)
                return redirect(url_for('index'))
            except Exception as e:
                return render_template('upload.html', error_message=f"An error occurred while saving the file: {str(e)}")
        else:
            return render_template('upload.html', error_message="Allowed file types are txt, csv, xls, xlsx")

    return render_template('upload.html')

def read_file_from_tmp(filename):
    print('Inside read file from tmp func')
    global df
    file_path = os.path.join('tmp', filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No such file: '{file_path}'")

    if filename.endswith('.xls') or filename.endswith('.xlsx'):
        df = pd.read_excel(file_path)
    elif filename.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file type")

    return df


@app.route('/index', methods=['GET', 'POST'])
def index():
    global df
    print('inside index')
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        filename = session.get('uploaded_filename')
        
        if not filename:
            return render_template('index.html', error_message="No file has been uploaded.")

        try:
            # df = read_file_from_tmp(filename)
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

            # c2p = chat2plot(df, chat=ChatOpenAI(model='gpt-4o'))
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
