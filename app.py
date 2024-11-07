from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import random
from os import path
import numpy as np
import socket
from flask import send_from_directory
from glob import glob
from flask_ngrok import run_with_ngrok

app = Flask(__name__)
run_with_ngrok(app)

app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///results.db'
db = SQLAlchemy(app)

@app.route('/clear')
def clear_session():
    session.clear()
    return "Session cleared!"

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    group_id = db.Column(db.Integer, nullable=False)
    response = db.Column(db.String(20), nullable=False)
    dataset = db.Column(db.String(50), nullable=False)
    images = db.Column(db.Text, nullable=False)
    completion_time = db.Column(db.Integer)

class DatasetFrequency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dataset_name = db.Column(db.String(50), unique=True, nullable=False)
    frequency = db.Column(db.Integer, default=0)


with app.app_context():
    db.create_all()

    # Initialize dataset frequencies if they don't exist
    default_datasets = [
        'dcface-gen', 'synface-gen', 'digiface-gen', 'sface-gen',
        'hsface10k-gen', 'idiff-face-gen', 'casia-webface-gen',
        'dcface-imp', 'synface-imp', 'digiface-imp', 'sface-imp',
        'hsface10k-imp', 'idiff-face-imp', 'casia-webface-imp',
    ]

    for dataset in default_datasets:
        if not DatasetFrequency.query.filter_by(dataset_name=dataset).first():
            db.session.add(DatasetFrequency(dataset_name=dataset, frequency=0))
    db.session.commit()


def get_dataset_frequencies():
    frequencies = DatasetFrequency.query.all()
    return {freq.dataset_name: freq.frequency for freq in frequencies}


def increment_dataset_frequency(dataset_name):
    dataset_freq = DatasetFrequency.query.filter_by(dataset_name=dataset_name).first()
    if dataset_freq:
        dataset_freq.frequency += 1
        db.session.commit()


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def print_dataset_frequencies():
    frequencies = DatasetFrequency.query.all()
    print("\nDataset Frequencies:")
    print("-" * 40)
    print(f"{'Dataset Name':<30} {'Frequency':>8}")
    print("-" * 40)
    for freq in frequencies:
        print(f"{freq.dataset_name:<30} {freq.frequency:>8}")
    print("-" * 40)


def select_random_dataset():
    print_dataset_frequencies()
    # Query datasets with frequency less than 5
    eligible_datasets = DatasetFrequency.query.filter(DatasetFrequency.frequency < 5).all()
    if not eligible_datasets:
        return "dcface"  # Default dataset if all have frequency >= 5

    # Randomly select one of the eligible datasets
    selected_dataset = random.choice(eligible_datasets)
    return selected_dataset.dataset_name


def preload_image_sets(dataset="dcface"):
    static_folder = path.join(app.root_path, 'static')
    all_folders = glob(static_folder + f"/{dataset}/*")

    image_sets = []
    for folder in all_folders:
        image_set = [path.relpath(im, static_folder).replace("\\", "/") for im in glob(folder + "/*")[:8]]
        image_sets.append(image_set)
    return image_sets


@app.route('/')
def home():
    if 'example_completed' in session:
        return redirect(url_for('index'))
    return render_template('home.html')


@app.route('/examples/<path:filename>')
def examples(filename):
    return send_from_directory('examples', filename)


@app.route('/examples/<int:example_num>')
def example(example_num):
    if example_num < 1 or example_num > 4:
        return redirect(url_for('home'))
    # Example data structure
    examples = {
        1: {
            'images': [url_for('examples', filename='not_sure_case.png')],
            'answer': 'Not Sure',
            'explanation': 'The first image is '
        },
        2: {
            'images': [url_for('examples', filename='not_sure_case1.png')],
            'answer': 'Not Sure',
            'explanation': 'These images clearly show different individuals with distinct facial features.'
        },
        3: {
            'images': [url_for('examples', filename='definitely_no.png')],
            'answer': 'Definitely No',
            'explanation': 'The first image in the first and second rows are from different race groups, so Definitely No.'
        },
        4: {
            'images': [url_for('examples', filename='definitely_no1.png')],
            'answer': 'Definitely No',
            'explanation': 'There are males and females among these images, so Definitely No.'
        }
    }

    return render_template('example.html',
                           example=examples[example_num],
                           current_num=example_num,
                           total_examples=len(examples))


@app.route('/break')
def break_page():
    return render_template('break.html')


@app.route('/start_study')
def start_study():
    session['example_completed'] = True
    if 'user_id' not in session:
        session['user_id'] = str(random.randint(10000, 99999))
        session['current_group'] = 0
        session['responses'] = {}
        session['dataset'] = select_random_dataset()

        # Increment the dataset frequency when submitting results
        increment_dataset_frequency(session['dataset'])

        while 'imp' in session['dataset']:
            session['dataset'] = select_random_dataset()

    return redirect(url_for('index'))


# Modified index route to check for example completion
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'example_completed' not in session:
        return redirect(url_for('home'))

    global IMAGE_SETS
    IMAGE_SETS = preload_image_sets(session['dataset'])

    if request.method == 'POST':
        action = request.form.get('action')
        response = request.form.get('response')
        elapsed_time = request.form.get('elapsed_time')  # Get elapsed time from form

        if response:
            session['responses'][str(session['current_group'])] = response
            session.modified = True

        if action == 'prev':
            session['current_group'] = max(session['current_group'] - 1, 0)
        elif action == 'next':
            session['current_group'] = min(session['current_group'] + 1, 99)
        elif action == 'submit':
            # Store elapsed time in session before redirecting
            session['elapsed_time'] = elapsed_time
            return redirect(url_for('submit'))

    images = IMAGE_SETS[session['current_group']]
    previous_response = session['responses'].get(str(session['current_group']), '')
    is_last_page = session['current_group'] == 1

    return render_template('index.html',
                         images=images,
                         group=session['current_group'] + 1,
                         total_groups=100,
                         previous_response=previous_response,
                         is_last_page=is_last_page)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        responses = session.get('responses', {})
        dataset = session.get('dataset', None)
        completion_time = session.get('elapsed_time')
        try:
            for group_id, response in responses.items():
                images = IMAGE_SETS[int(group_id)]
                result = Result(
                    user_id=session['user_id'],
                    group_id=int(group_id),
                    response=response,
                    dataset=dataset,
                    images=','.join(images),
                    completion_time=int(completion_time) if completion_time else None
                )
                db.session.add(result)
            db.session.commit()
            session.clear()
            return "You can close this tab!"
        except Exception as e:
            db.session.rollback()
            return f"An error occurred: {str(e)}"

    # Pass the elapsed time to the submit template
    elapsed_time = session.get('elapsed_time')
    return render_template('submit.html', elapsed_time=elapsed_time)


if __name__ == '__main__':
    ip = get_ip()
    app.run(host='0.0.0.0', port=5000, debug=True)
