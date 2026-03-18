from flask import Flask, request, jsonify
import logging
import requests
from config import API_KEY, promt

CHAD_API_KEY = API_KEY

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# База данных пользователей (в продакшене используйте настоящую БД)
users_db = {}


@app.route('/')
def main():
    return 'Тест'



def make_response(text, end_session=False, buttons=None):
    """Создать ответ для Алисы"""
    response = {
        "version": request.json['version'],
        "session": request.json['session'],
        "response": {
            "text": text,
            "end_session": end_session
        }
    }
    if buttons:
        response["response"]["buttons"] = buttons

    return jsonify(response)

def create_user(user_id):
    users_db[user_id] = {
        "level_tested": False,
        "level": None,
        "correct_answers": 0,
        "total_questions": 0,
        "current_word": None,
        "last_word": None,
        "last_cond": None
    }

def make_word(last_word: str, last_cond: bool):
    promt = (f"Отвечай очень быстро!"
             f"Дай одно английское слово'."
             f"Предыдущее слово было '{last_word}'. "
             f"Слово должно быть {'сложнее' if {last_cond} else 'легче'} предыдущего. "
             f"Нужно написать только слово! без запятых и других знаков")
    request_json = {
        "message": promt,
        "api_key": CHAD_API_KEY
    }
    response = requests.post(url='https://ask.chadgpt.ru/api/public/gpt-5-nano',json=request_json)
    resp_json = response.json()
    return resp_json['response']

def word_transl(word: str):
    request_json = {
        "message": (f"как переводится {word} на русский? Напиши толко 1 слово без знаков препинания и других слов!"),
        "api_key": CHAD_API_KEY
    }
    resp = requests.post(url='https://ask.chadgpt.ru/api/public/gpt-5-nano', json=request_json)
    resp_json = resp.json()
    return resp_json['response']

def check_answer(word: str, ans: str) -> bool:
    request_json = {
        "message": (f"переводится ли слово {word}, как {ans}? Ответь yes/no"),
        "api_key": CHAD_API_KEY,
        "history": [
            {"role": "system", "content": "ты должен ответить или yes, или no, без дополнительного текста и символов"}]
    }
    resp = requests.post(url='https://ask.chadgpt.ru/api/public/gpt-5-nano', json=request_json)
    resp_json = resp.json()
    if  resp_json["response"] == "yes":
        return True
    else:
        return False


@app.route('/alice', methods=['POST'])
def alice_webhook():

    logging.info(f"Request: {request.json}")

    # Получаем данные из запроса
    user_id = request.json['session']['user_id']
    command = request.json['request']['original_utterance'].strip()
    is_new_session = request.json['session']['new']

    # Проверяем, есть ли пользователь в базе
    if user_id not in users_db:
        create_user(user_id)

    user = users_db[user_id]

    # Если это новая сессия
    if is_new_session:
        if user['level_tested']:
            return make_response("Привет! Чем хочешь заняться?", end_session=False)
        else:
            user['total_questions'] = 0
            user['correct_answers'] = 0
            word = make_word("qualification", False)
            user['current_word'] = word
            user["last_word"] = word
            user['total_questions'] = 1
            print(f"Привет! Я помогу определить твой уровень английского. "
                f"Я задам тебе 10 вопросов. Переведи слово на русский: '{word}'")
            return make_response(
                f"Привет! Я помогу определить твой уровень английского. "
                f"Я задам тебе 10 вопросов. Переведи слово на русский: '{word}'",
                end_session=False
            )

    # Если пользователь проходит тест уровня
    if not user['level_tested'] and user['total_questions'] > 0:

        word = make_word(user["last_word"], user["last_cond"])
        user['current_word'] = word
        user["last_word"] = word

        current_word = user['current_word']

        # Проверяем ответ
        is_correct = check_answer(command, current_word)

        if is_correct:
            user['correct_answers'] += 1
            user['last_cond'] = True
        else:
            user['last_cond'] = False

        # Проверяем, закончился ли тест
        if user['total_questions'] >= 10:
            user['level_tested'] = True
            correct = user['correct_answers']

            if correct >= 9:
                user['level'] = "C1+"
            elif correct >= 7:
                user['level'] = "B2"
            elif correct >= 5:
                user['level'] = "B1"
            elif correct >= 3:
                user['level'] = "A2"
            else:
                user['level'] = "A1"

            return make_response(
                f"Тест завершен! Ты ответил правильно на {correct} из 10 вопросов. "
                f"Твой уровень: {user['level']}. Чем хочешь заняться?",
                end_session=False
            )
        else:

            if is_correct:
                print(f"Правильно! Следующее слово: '{word}")
                response_text = f"Правильно! Следующее слово: '{word}'"
            else:
                transl = word_transl(word)


                response_text = f"Неправильно. '{current_word}' - это '{transl}'. Следующее слово: '{word}'"
                print(response_text)


            return make_response(response_text, end_session=False)

    # Если пользователь уже прошел тест
    return make_response("Чем хочешь заняться?", end_session=False)


@app.route('/ping', methods=['GET'])
def ping():
    """Проверка работоспособности сервера"""
    return "pong"


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=4000)