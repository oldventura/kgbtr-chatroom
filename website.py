#!/usr/bin/python
# -*- encoding:utf-8 -*-

import json
import os
import secrets
import time

from flask import Flask, redirect, render_template, request, session, abort
from flask_socketio import SocketIO, emit, join_room, leave_room
from markupsafe import escape
from ratelimit import limits

app = Flask(__name__, template_folder='static')
app.secret_key = secrets.token_hex(32)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
app.users     = []
app.auth      = {}
app.blacklist = []

socketio = SocketIO(app)

_CALLS = 100
_PERIOD = 60

_SCALLS = 10
_SPERIOD = 60

# Load registered users
# Just until reddit login is ready
if 'users.json' in os.listdir('.'):
    with open('users.json', 'r') as f:
        app.auth = json.load(f)

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
            print(f"{escape(session['username'])}", request.headers.get('X-Forwarded-For', request.remote_addr))
            if not session['last'] or int(time.time()) - int(session['last']) > 5:
                if escape(session['username']) in app.auth.keys():
                    approved = True
                else:
                    approved = False

                emit('incoming', {
                    "approved": approved,
                    "username": escape(session['username']),
                    "message": escape(data['message'][:128]),
                }, to='KGBTR')
                session['last'] = time.time()

# PAGES

# Block banned ip addresses
@app.before_request
def block_method():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip in app.blacklist:
        abort(403)

@app.route("/", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def index():
    if 'username' in session:
        return render_template("index.html", username=session['username'])
    else:
        return redirect("/login")

@app.route("/ban/<key>/<ip>", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def ban_address(key, ip):
    if request.method == 'GET':
        if key == app.secret_key:
            app.blacklist.append(ip)
            print(f"IP: [{ip}] added to blacklist.")
            data = {"status": "success"}
            return data, 401

@app.route("/login", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def login():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        return render_template("login.html")

@app.route("/get_secret", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def get_secret():
    if request.method == 'GET':
        print(f"SECRET: [{app.secret_key}]")

@app.route("/login_username/<key>", methods=["GET"])
@limits(calls=_SCALLS, period=_SPERIOD)
def login_username(key):
    if not key:
        return redirect("/login")

    if request.method == 'GET':
        return render_template("login_user.html", secret_key=key)
    else:
        return render_template("login_user.html", secret_key=key)


@app.route("/check_username", methods=["POST"])
@limits(calls=_CALLS, period=_PERIOD)
def check():
    form = request.form
    if 'username' in form.keys():
        if escape(form['username'])[:20] not in app.users and escape(form['username'])[:20] not in app.auth.keys():
            session['username'] = escape(request.form['username'])[:20]
            session['last'] = None
            data = {"status": "success"}
            return data, 200

        elif escape(form['username'])[:20] not in app.users and escape(form['username'])[:20] in app.auth.keys():
            data = {"status": "unauthorized"}
            return data, 401

        else:
            data = {"status": "failure"}
            return data, 401
    data = {"status": "failure"}
    return data, 401


@app.route("/login_with_username", methods=["POST"])
@limits(calls=_SCALLS, period=_SPERIOD)
def check_login():
    form = request.form
    if 'username' in form.keys() and 'password' in form.keys():
        if form['username'] not in app.auth.keys():
            data = {"status": "failure"}
            return data, 401
        
        if form['username'] in app.auth.keys() and form['password'] == app.auth[form['username']]:
            session['username'] = request.form['username']
            session['last'] = None
            data = {"status": "success"}
            return data, 200
        
    data = {"status": "failure"}
    return data, 401



# Static Content


@app.route('/favicon.svg', methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def favicon():
    return app.send_static_file("images/favicon.svg")
