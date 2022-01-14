#!/usr/bin/python
# -*- encoding:utf-8 -*-

import secrets

from flask import Flask, render_template, request, session, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
from ratelimit import limits

app = Flask(__name__, template_folder='static')
app.secret_key = secrets.token_hex(32)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
app.users = []

socketio = SocketIO(app)

_CALLS = 100
_PERIOD = 60

# SocketIO


@socketio.on('joinRoom')
def join_user_into_room(data=None):
    if 'username' in session:
        if data:
            # Join Room
            join_room('KGBTR')

            # Add user to online users
            if session['username'] not in app.users:
                app.users.append(session['username'])

            # Send online user count
            emit('online_count', {
                "count": len(app.users),
            }, to='KGBTR')


@socketio.on('disconnect')
def handle_on_disconnect():
    if 'username' in session:
        # Remove user from online users
        app.users.remove(session['username'])

        # Send online user count
        emit('online_count', {
            "count": len(app.users),
        }, to='KGBTR')

        # Leave Room
        leave_room('KGBTR')

        # Remove username from session
        session.pop('username', None)


@socketio.on('message')
def handle_json(data=None):
    if 'username' in session:
        if data:
            emit('incoming', {
                "username": session['username'],
                "message": data['message'],
            }, to='KGBTR')

# PAGES


@app.route("/", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def index():
    if 'username' in session:
        return render_template("index.html", username=session['username'])
    else:
        return redirect("/login")


@app.route("/login", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def login():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        return render_template("login.html")


@app.route("/check_username", methods=["POST"])
@limits(calls=_CALLS, period=_PERIOD)
def check():
    form = request.form
    if 'username' in form.keys():
        if form['username'] not in app.users:
            session['username'] = request.form['username']
            data = {"status": "success"}
            return data, 200
        else:
            data = {"status": "failure"}
            return data, 401

# Static Content


@app.route('/favicon.svg', methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def favicon():
    return app.send_static_file("images/favicon.svg")
