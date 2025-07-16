from flask import Flask, request, jsonify, render_template
import json
from difflib import get_close_matches
import random
import requests
from bs4 import BeautifulSoup
import re
import threading
import time
import os

app = Flask(__name__)

with open('knowledge_base.json', 'r') as f:
    knowledge_base = json.load(f)

# Basic Q&A helpers
def find_best_match(user_question, questions):
    matches = get_close_matches(user_question.lower(), [q.lower() for q in questions], n=1, cutoff=0.65)
    return matches[0] if matches else None

def get_answer_for_question(question, knowledge_base):
    for q in knowledge_base["questions"]:
        if q["question"].lower() == question.lower():
            return q["answer"]
    return None

# --- New Features ---

# Lie detector analysis (simplified)
hedge_words = ["maybe", "perhaps", "possibly", "could be", "might be", "i guess", "i suppose", "i think",
               "i’m not sure", "not really", "kind of", "sort of", "more or less", "i’d say",
               "it seems like", "as far as i remember", "i believe", "to some extent", "you could say that",
               "depends", "that’s hard to say", "let’s just say", "i wouldn’t say that exactly",
               "not exactly", "not technically", "in a way", "something like that", "i don’t know",
               "i mean", "i guess you could say", "just", "only", "barely", "hardly", "a little",
               "not that much", "nothing major", "no big deal", "wasn’t serious", "sorta", "kinda",
               "a tiny bit", "at some point", "a while back", "recently", "i think it was yesterday",
               "not sure when", "back then", "sometime", "earlier maybe", "can’t remember exactly", "..",
               "wasn't", "*"]
contradiction_phrases = [("yes", "no"), ("never", "sometimes"), ("always", "not always")]

def analyze_message(msg):
    score = 0
    text = msg.lower()

    # Hedge words
    if any(hw in text for hw in hedge_words):
        score += 2

    # Short/cryptic message
    if len(text.split()) < 4:
        score += 1

    # Contradictions
    for a, b in contradiction_phrases:
        if a in text and b in text:
            score += 2

    # Avoidance
    if any(p in text for p in ["idk", "don't wanna say", "prefer not to answer"]):
        score += 3

    if "?" in text:
        score -= 0.5

    return score

def lie_detector_analysis(messages):
    # messages: list of dict {"speaker": str, "message": str}
    scores = {}
    for entry in messages:
        speaker = entry.get("speaker")
        message = entry.get("message", "")
        score = analyze_message(message)
        if speaker not in scores:
            scores[speaker] = []
        scores[speaker].append(score)
    summary = {}
    for speaker, vals in scores.items():
        avg = sum(vals) / len(vals)
        if avg > 1.2:
            verdict = "Highly Suspicious"
        elif avg > 0.5:
            verdict = "Suspicious"
        else:
            verdict = "Likely Truthful"
        summary[speaker] = {"average_score": avg, "verdict": verdict}
    return summary


# Rock paper scissors logic
def rps_play(player_choice):
    choices = ["rock", "paper", "scissors"]
    player_choice = player_choice.lower()
    if player_choice not in choices:
        return {"error": "Invalid choice. Choose rock, paper, or scissors."}

    comp_choice = random.choice(choices)
    if player_choice == comp_choice:
        result = "tie"
    elif (player_choice == "rock" and comp_choice == "scissors") or \
         (player_choice == "paper" and comp_choice == "rock") or \
         (player_choice == "scissors" and comp_choice == "paper"):
        result = "win"
    else:
        result = "lose"
    return {"player": player_choice, "computer": comp_choice, "result": result}

# Wikipedia search snippet
def get_wiki_intro(topic):
    url = f"https://simple.wikipedia.org/wiki/{topic.replace(' ', '_')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        return "Sorry, I couldn't find that topic."
    soup = BeautifulSoup(res.text, 'html.parser')

    paragraphs = soup.select('#mw-content-text p')
    text = ' '.join(p.get_text() for p in paragraphs if p.get_text().strip())

    lines = text.split('. ')
    summary = '. '.join(lines[:3]) + '.' if lines else "No summary available."
    return summary

# Dice roll
def roll_dice():
    return random.randint(1,6)

# Alarm (Note: no direct cross-platform alarm in Flask, but can simulate delay + response)
alarms = {}

def set_alarm(minutes, message):
    def alarm_thread():
        time.sleep(minutes * 60)
        alarms[message] = f"Alarm: {message} (set {minutes} minutes ago)!"
    threading.Thread(target=alarm_thread, daemon=True).start()
    return f"Alarm set for {minutes} minutes from now with message: '{message}'"

# --- Routes ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_input = data.get('message', '').strip()

    commands = ['play rps', 'rock paper scissors', 'lie detector', 'search', 'dice roll', 'set alarm']

    # Detect commands crudely
    lowered = user_input.lower()
    if any(cmd in lowered for cmd in ['play rps', 'rock paper scissors']):
        return jsonify({'response': 'To play, send POST to /play-rps with your choice (rock, paper, or scissors).'})

    if 'lie detector' in lowered:
        return jsonify({'response': 'Send conversation messages to /lie-detector as JSON to analyze.'})

    if 'search' in lowered:
        return jsonify({'response': 'Send your search topic to /search as JSON to get Wikipedia intro.'})

    if 'dice roll' in lowered:
        result = roll_dice()
        return jsonify({'response': f'🎲 You rolled a {result}.'})

    if 'set alarm' in lowered:
        return jsonify({'response': 'Send POST to /set-alarm with minutes and message in JSON.'})

    # Otherwise regular Q&A
    questions = [q["question"] for q in knowledge_base["questions"]]
    best_match = find_best_match(user_input, questions)

    if best_match:
        answer = get_answer_for_question(best_match, knowledge_base)
    else:
        answer = "I don't understand."

    return jsonify({'response': answer})

@app.route('/play-rps', methods=['POST'])
def play_rps():
    data = request.get_json()
    choice = data.get('choice', '')
    result = rps_play(choice)
    if 'error' in result:
        return jsonify({'response': result['error']})
    return jsonify({'response': f"Your choice: {result['player']}. Computer chose: {result['computer']}. Result: {result['result'].capitalize()}!"})

@app.route('/lie-detector', methods=['POST'])
def lie_detector():
    data = request.get_json()
    messages = data.get('messages', [])
    if not isinstance(messages, list):
        return jsonify({'response': 'Invalid input. Send a list of messages with speaker and message.'})
    summary = lie_detector_analysis(messages)
    return jsonify({'response': summary})

@app.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    topic = data.get('topic', '')
    if not topic:
        return jsonify({'response': 'Please provide a topic to search.'})
    summary = get_wiki_intro(topic)
    return jsonify({'response': summary})

@app.route('/set-alarm', methods=['POST'])
def alarm():
    data = request.get_json()
    try:
        minutes = int(data.get('minutes', 0))
        message = data.get('message', '')
        if minutes <= 0 or not message:
            raise ValueError
    except Exception:
        return jsonify({'response': 'Invalid input. Provide positive minutes and a message.'})
    reply = set_alarm(minutes, message)
    return jsonify({'response': reply})

# Run app
if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
