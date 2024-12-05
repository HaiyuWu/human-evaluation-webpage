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


# Modified database models
class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    group_id = db.Column(db.Integer, nullable=False)
    response = db.Column(db.String(20), nullable=False)
    folder_paths = db.Column(db.Text, nullable=False)  # Store the selected folder paths
    images = db.Column(db.Text, nullable=False)
    completion_time = db.Column(db.Integer)


class FolderFrequency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dataset_name = db.Column(db.String(50), nullable=False)
    folder_path = db.Column(db.String(255), unique=True, nullable=False)
    frequency = db.Column(db.Integer, default=0)


with app.app_context():
    db.create_all()

    # Initialize folder frequencies if they don't exist
    static_folder = path.join(app.root_path, 'static')
    datasets = [
        'dcface-gen', 'synface-gen', 'digiface-gen', 'sface-gen',
        'hsface10k-gen', 'idiff-face-gen', 'casia-webface-gen',
        'dcface-imp', 'synface-imp', 'digiface-imp', 'sface-imp',
        'hsface10k-imp', 'idiff-face-imp', 'casia-webface-imp'
    ]

    for dataset in datasets:
        dataset_folders = glob(path.join(static_folder, dataset, "*"))
        for folder in dataset_folders:
            rel_path = path.relpath(folder, static_folder).replace("\\", "/")
            if not FolderFrequency.query.filter_by(folder_path=rel_path).first():
                db.session.add(FolderFrequency(
                    dataset_name=dataset,
                    folder_path=rel_path,
                    frequency=0
                ))
    db.session.commit()


def increment_folder_frequencies(folder_paths):
    """Increment the frequency count for selected folders"""
    for folder_path in folder_paths:
        folder_freq = FolderFrequency.query.filter_by(folder_path=folder_path).first()
        if folder_freq:
            folder_freq.frequency += 1
    db.session.commit()


def print_folder_frequencies():
    """Print current folder frequencies for monitoring"""
    frequencies = FolderFrequency.query.all()
    print("\nFolder Frequencies:")
    print("-" * 80)
    print(f"{'Dataset':<20} {'Folder Path':<40} {'Frequency':>10}")
    print("-" * 80)
    for freq in frequencies:
        print(f"{freq.dataset_name:<20} {freq.folder_path:<40} {freq.frequency:>10}")
    print("-" * 80)


def select_folders_for_session():
    """Select 15 folders from each pair of gen/imp datasets, prioritizing least used folders"""
    static_folder = path.join(app.root_path, 'static')
    selected_folders = []

    # List of base dataset names (without -gen/-imp suffix)
    base_datasets = [
        'dcface', 'synface', 'digiface', 'sface',
        'hsface10k', 'idiff-face', 'casia-webface'
    ]

    for base_dataset in base_datasets:
        # Get folders from both gen and imp versions
        gen_folders = FolderFrequency.query.filter_by(dataset_name=f"{base_dataset}-gen") \
            .order_by(FolderFrequency.frequency) \
            .all()
        imp_folders = FolderFrequency.query.filter_by(dataset_name=f"{base_dataset}-imp") \
            .order_by(FolderFrequency.frequency) \
            .all()

        # Combine and sort by frequency
        all_folders = sorted(gen_folders + imp_folders, key=lambda x: x.frequency)

        # Select the 15 folders with lowest frequency
        selected = all_folders[:15]
        selected_folders.extend([folder.folder_path for folder in selected])

    # Shuffle the selected folders
    random.shuffle(selected_folders)
    return selected_folders


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def preload_image_sets():
    """Load images from selected folders for the session"""
    if 'selected_folders' not in session:
        session['selected_folders'] = select_folders_for_session()
        increment_folder_frequencies(session['selected_folders'])
        print_folder_frequencies()  # Print frequencies for monitoring

    static_folder = path.join(app.root_path, 'static')
    image_sets = []

    for folder_path in session['selected_folders']:
        full_folder_path = path.join(static_folder, folder_path)
        image_set = [path.relpath(im, static_folder).replace("\\", "/")
                     for im in glob(full_folder_path + "/*")[:8]]
        image_sets.append(image_set)

    return image_sets


@app.route('/clear')
def clear_session():
    session.clear()
    return "Session cleared!"


@app.route('/')
def home():
    if not session.get('consented'):
        return redirect(url_for('consent'))
    if 'example_completed' in session:
        return redirect(url_for('index'))
    return render_template('home.html')


@app.route('/consent')
def consent():
    if session.get('consented'):
        return redirect(url_for('home'))
    return render_template('consent.html')


@app.route('/handle_consent', methods=['POST'])
def handle_consent():
    consent = request.form.get('consent')
    if consent == 'accept':
        session['consented'] = True
        return redirect(url_for('home'))
    else:
        return redirect(url_for('thank_you'))


@app.route('/thank_you')
def thank_you():
    return render_template('thank_you.html')


@app.route('/examples/<path:filename>')
def examples(filename):
    return send_from_directory('examples', filename)


@app.route('/examples/<int:example_num>')
def example(example_num):
    if example_num < 1 or example_num > 4:
        return redirect(url_for('home'))
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
    return redirect(url_for('index'))


@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'example_completed' not in session:
        return redirect(url_for('home'))

    global IMAGE_SETS
    IMAGE_SETS = preload_image_sets()

    if request.method == 'POST':
        action = request.form.get('action')
        response = request.form.get('response')
        elapsed_time = request.form.get('elapsed_time')

        if response:
            session['responses'][str(session['current_group'])] = response
            session.modified = True

        if action == 'prev':
            session['current_group'] = max(session['current_group'] - 1, 0)
        elif action == 'next':
            session['current_group'] = min(session['current_group'] + 1, 104)
        elif action == 'submit':
            session['elapsed_time'] = elapsed_time
            return redirect(url_for('submit'))

    images = IMAGE_SETS[session['current_group']]
    previous_response = session['responses'].get(str(session['current_group']), '')
    is_last_page = session['current_group'] == 104

    return render_template('index.html',
                           images=images,
                           group=session['current_group'] + 1,
                           total_groups=105,
                           previous_response=previous_response,
                           is_last_page=is_last_page)


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        responses = session.get('responses', {})
        completion_time = session.get('elapsed_time')
        try:
            for group_id, response in responses.items():
                images = IMAGE_SETS[int(group_id)]
                result = Result(
                    user_id=session['user_id'],
                    group_id=int(group_id),
                    response=response,
                    folder_paths=session['selected_folders'][int(group_id)],
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

    elapsed_time = session.get('elapsed_time')
    return render_template('submit.html', elapsed_time=elapsed_time)


if __name__ == '__main__':
    ip = get_ip()
    app.run(host='0.0.0.0', port=8000, debug=True, ssl_context=None)