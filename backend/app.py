import os
import io
import zipfile
import shutil
import logging
import numpy as np
from collections import defaultdict
from PIL import Image
import cv2
from mtcnn import MTCNN
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image

# Конфигурация
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MIN_CONFIDENCE = 0.3
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_IMAGE_DIMENSION = 4000
PRE_RESIZE_DIMENSION = 1024

# Инициализация Flask - приложения
app = Flask(__name__)
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Логирование конфигурации
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка моделей
try:
    model = MobileNetV2(weights='imagenet')#Основная классификация
    face_detector = MTCNN()#Детекция лиц
    logger.info("Модель успешно загружена!")#Логирование
except Exception as e:
    logger.error(f"Ошибка загузки модели: {str(e)}")#Логирование
    raise


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_image_read(img_path):
    try:
        with Image.open(img_path) as img:
            if max(img.size) > MAX_IMAGE_DIMENSION: # Защита от больших файлов
                logger.warning(f"Изображение слишком большое: {img.size}")
                return None

            if img.mode != 'RGB':
                img = img.convert('RGB') # Конвертация в RGB

            return np.array(img) # Преобразование в numpy array
    except Exception as e:
        logger.error(f"Ошибка в чтении изображения: {str(e)}")
        return None


def resize_image(img_array, target_size):
    try:
        h, w = img_array.shape[:2]
        # Предварительное уменьшение для больших изображений
        if max(h, w) > PRE_RESIZE_DIMENSION: # PRE_RESIZE_DIMENSION = 1024
            scale = PRE_RESIZE_DIMENSION / max(h, w)
            img_array = cv2.resize(img_array, (0, 0), fx=scale, fy=scale)
        # Финальный ресайз для модели
        return cv2.resize(img_array, target_size) # (224, 224) для MobileNetV2
    except Exception as e:
        logger.error(f"Ошибка форматирования: {str(e)}")
        return None


def contains_faces(img_path):
    try:
        img_array = safe_image_read(img_path)
        if img_array is None:
            return False

        img_array = resize_image(img_array, (800, 800))
        if img_array is None:
            return False

        faces = face_detector.detect_faces(img_array)
        return len(faces) > 0
    except Exception as e:
        logger.error(f"Ошибка обнаружения лица: {str(e)}")
        return False


def classify_image(img_path):
    try:
        classes = []

        # Приоритетная детекция лиц
        if contains_faces(img_path):
            classes.append({'label': 'person', 'confidence': 0.95})

        # Основная классификация
        img_array = safe_image_read(img_path)
        if img_array is None:
            return [{'label': 'other', 'confidence': 0.0}]

        img_array = resize_image(img_array, (224, 224))
        if img_array is None:
            return [{'label': 'other', 'confidence': 0.0}]

        img_array = np.expand_dims(img_array, axis=0)
        img_array = preprocess_input(img_array)

        predictions = model.predict(img_array, verbose=0)
        decoded_preds = decode_predictions(predictions, top=5)[0]

        car_categories = [
            'car', 'minivan', 'truck', 'pickup', 'racer', 'convertible',
            'limousine', 'sports_car', 'model_t', 'ambulance', 'beach_wagon'
        ]

        car_confidences = [float(pred[2]) for pred in decoded_preds if
                           pred[1] in car_categories and pred[2] >= MIN_CONFIDENCE]
        if car_confidences:
            classes.append({'label': 'car', 'confidence': max(car_confidences)})

        for pred in decoded_preds:
            if (pred[2] >= MIN_CONFIDENCE and
                    pred[1] not in car_categories and
                    not any(c['label'] == 'person' for c in classes)):
                classes.append({
                    'label': pred[1],
                    'confidence': float(pred[2])
                })

        return classes
    except Exception as e:
        logger.error(f"Ошибка классификации: {str(e)}")
        return [{'label': 'other', 'confidence': 0.0}]


def get_album_names(predictions):
    albums = set()
    for pred in predictions:
        label_lower = pred['label'].lower()
        confidence = pred['confidence']

        # Люди
        people_terms = [
            'person', 'man', 'woman', 'child', 'baby', 'boy', 'girl', 'human',
            'face', 'head', 'eye', 'nose', 'mouth', 'hand', 'finger', 'foot',
            'bride', 'groom', 'athlete', 'player', 'singer', 'dancer', 'worker',
            'doctor', 'nurse', 'student', 'teacher', 'chef', 'soldier', 'pilot',
            'artist', 'audience', 'crowd', 'team', 'couple', 'family'
        ]
        if any(term in label_lower for term in people_terms):
            albums.add('Люди')

        # Машины и транспорт
        vehicle_terms = [
            'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'train', 'ambulance',
            'fire_engine', 'minivan', 'pickup', 'racer', 'convertible', 'limousine',
            'taxi', 'tow_truck', 'tractor', 'forklift', 'snowmobile', 'streetcar',
            'locomotive', 'submarine', 'sailboat', 'yacht', 'ship', 'aircraft_carrier',
            'airplane', 'helicopter', 'balloon', 'spaceship', 'rocket', 'sled', 'skateboard'
        ]
        if any(term in label_lower for term in vehicle_terms):
            albums.add('Машины и транспорт')

        # Животные
        animal_terms = [
            'animal', 'dog', 'cat', 'bird', 'fish', 'tiger', 'lion',
            'elephant', 'bear', 'zebra', 'giraffe', 'wolf', 'fox',
            'rabbit', 'squirrel', 'horse', 'cow', 'sheep', 'pig',
            'monkey', 'panda', 'kangaroo', 'deer', 'camel', 'gorilla',
            'leopard', 'rhinoceros', 'hippopotamus', 'crocodile', 'turtle',
            # Породы собак
            'greyhound', 'retriever', 'poodle', 'terrier', 'bulldog',
            'chihuahua', 'husky', 'dalmatian', 'boxer', 'beagle',
            'doberman', 'rottweiler', 'shepherd', 'malamute', 'spaniel',
            'italian greyhound', 'shih-tzu', 'pug', 'collie', 'schnauzer',
            # Породы кошек
            'tabby', 'siamese', 'persian', 'ragdoll', 'bengal',
            'sphynx', 'maine coon', 'british shorthair', 'scottish fold',
            # Другие животные
            'parrot', 'eagle', 'owl', 'penguin', 'flamingo', 'peacock',
            'swan', 'duck', 'sparrow', 'pigeon', 'falcon', 'vulture',
            'shark', 'whale', 'dolphin', 'octopus', 'jellyfish', 'lobster'
        ]
        if any(term in label_lower for term in animal_terms):
            albums.add('Животные')

        # Природа
        nature_terms = [
            'alp', 'cliff', 'valley', 'volcano', 'coral', 'geyser', 'lakeside', 'seashore',
            'sandbar', 'promontory', 'canyon', 'mountain', 'forest', 'woodland', 'grove',
            'jungle', 'thicket', 'desert', 'oasis', 'marsh', 'swamp', 'bog', 'fen',
            'tundra', 'glacier', 'iceberg', 'dune', 'hill', 'meadow', 'pasture', 'prairie',
            'field', 'orchard', 'vineyard', 'garden', 'park', 'lawn', 'flower', 'tree',
            'plant', 'palm', 'pine', 'oak', 'willow', 'maple', 'redwood', 'sequoia',
            'banana', 'bamboo', 'cactus', 'fern', 'moss', 'lichen', 'algae', 'kelp',
            'blossom', 'petal', 'stamen', 'pistil', 'leaf', 'branch', 'trunk', 'root',
            'river', 'stream', 'brook', 'creek', 'waterfall', 'rapids', 'whirlpool',
            'lake', 'pond', 'pool', 'lagoon', 'reservoir', 'bay', 'gulf', 'strait',
            'channel', 'fjord', 'sound', 'reef', 'atoll', 'island', 'peninsula', 'cape',
            'beach', 'shore', 'coast', 'seacoast', 'wave', 'tide', 'surf', 'spray',
            'horizon', 'sunset', 'sunrise', 'dusk', 'dawn', 'twilight', 'moonlight',
            'starlight', 'cloud', 'fog', 'mist', 'haze', 'rain', 'snow', 'hail', 'sleet',
            'frost', 'dew', 'lightning', 'thunder', 'storm', 'hurricane', 'tornado',
            'cyclone', 'typhoon', 'blizzard', 'avalanche', 'landslide', 'eruption',
            'lava', 'magma', 'crater', 'caldera', 'geyser', 'hotspring', 'fumarole',
            'stalactite', 'stalagmite', 'crystal', 'mineral', 'rock', 'stone', 'pebble',
            'boulder', 'sand', 'soil', 'clay', 'mud', 'gravel', 'silt', 'sediment'
        ]
        if any(term in label_lower for term in nature_terms):
            albums.add('Природа')

        # Для высокоуверенных предсказаний создаем отдельный альбом
        elif confidence >= 0.8:
            clean_label = pred['label'].replace('_', ' ').title()

    return list(albums) if albums else ['Другое']


def organize_files(results):
    try:
        for result in results:
            for album in result['albums']:
                album_path = os.path.join(app.config['UPLOAD_FOLDER'], album)
                os.makedirs(album_path, exist_ok=True)

                dest_path = os.path.join(album_path, result['filename'])
                if not os.path.exists(dest_path):
                    shutil.copy2(result['temp_path'], dest_path)

                result['paths'] = result.get('paths', {})
                result['paths'][album] = f"/uploads/{album}/{result['filename']}"

            if 'temp_path' in result:
                os.unlink(result['temp_path'])
                del result['temp_path']

        return True
    except Exception as e:
        logger.error(f"File organization error: {str(e)}")
        return False


def create_zip_archive(album_name):
    album_path = os.path.join(app.config['UPLOAD_FOLDER'], album_name) # Создание архива в памяти
    if not os.path.exists(album_path):
        return None

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(album_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, album_path)
                zf.write(file_path, arcname=os.path.join(album_name, arcname))

    memory_file.seek(0) # Сброс указателя
    return memory_file


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'files' not in request.files:
        return jsonify({'error': 'Нет файловой части'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'Нет выбранных файлов'}), 400

    results = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                file.save(temp_path)

                if os.path.getsize(temp_path) > MAX_FILE_SIZE:
                    os.unlink(temp_path)
                    results.append({
                        'filename': filename,
                        'error': 'File too large'
                    })
                    continue

                predictions = classify_image(temp_path)
                album_names = get_album_names(predictions)

                results.append({
                    'filename': filename,
                    'albums': album_names,
                    'predictions': predictions,
                    'temp_path': temp_path
                })
            except Exception as e:
                logger.error(f"Ошибка обработки {filename}: {str(e)}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                continue

    if not organize_files(results):
        return jsonify({'error': 'File organization failed'}), 500

    return jsonify(results), 200


@app.route('/albums', methods=['GET'])
def get_albums():
    albums = defaultdict(list)
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
        if root == app.config['UPLOAD_FOLDER']:
            continue

        album_name = os.path.basename(root)
        for file in files:
            if allowed_file(file):
                albums[album_name].append({
                    'filename': file,
                    'url': f"/uploads/{album_name}/{file}"
                })

    return jsonify(albums), 200


@app.route('/uploads/<path:album>/<filename>')
def uploaded_file(album, filename):
    try:
        return send_from_directory(
            os.path.join(app.config['UPLOAD_FOLDER'], album),
            filename
        )
    except Exception as e:
        logger.error(f"Ошибка подачи файла: {str(e)}")
        return jsonify({'error': str(e)}), 404


@app.route('/download/<album_name>', methods=['GET'])
def download_album(album_name):
    try:
        safe_album_name = secure_filename(album_name)
        zip_file = create_zip_archive(safe_album_name)

        if not zip_file:
            return jsonify({'error': 'Альбом не найден'}), 404

        return send_file(
            zip_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{safe_album_name}.zip'
        )
    except Exception as e:
        logger.error(f"Ошибка создания ZIP-архива: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/clear', methods=['DELETE'])
def clear_uploads():
    try:
        # Удаляем все содержимое папки uploads
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f'Ошибка при удалении {file_path}. Причина: {str(e)}')

        # Создаем пустую папку uploads заново
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        return jsonify({'success': True, 'message': 'Все фото и альбомы успешно удалены'}), 200
    except Exception as e:
        logger.error(f"Ошибка при очистке: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)


