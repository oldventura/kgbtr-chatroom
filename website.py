#!/usr/bin/python
# -*- encoding:utf-8 -*-

import json
import os
import secrets
import time

import praw
from flask import Flask, abort, redirect, render_template, request, session
from flask_socketio import SocketIO, disconnect, emit, join_room, leave_room
from markupsafe import escape
from ratelimit import limits

app = Flask(__name__, template_folder='static')
app.secret_key = secrets.token_hex(32)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
app.socketio = SocketIO(app)
app.address = "https://kgbtrchat.herokuapp.com"

# I didn't want to use a global reddit object
# because I believe it would slow down the
# processes when everyone tries to
# authorize through the same object.

# app.reddit = praw.Reddit(
#     "chatroom"
# )

app.auth = []
app.users = []
app.blacklist = []

# Add some users like moderators as 'approved',
# so that they will be marked with blue color

if 'users.json' in os.listdir('.'):
    with open('users.json', 'r') as f:
        content = json.load(f)
        app.auth = content['approved']
        app.blacklist = content['banned']

_CALLS = 100
_PERIOD = 60

# SocketIO


@app.socketio.on('joinRoom')
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
    else:
        disconnect()


@app.socketio.on('disconnect')
def handle_on_disconnect(data=None):
    if 'username' in session:
        # Remove user from online users
        if session['username'] in app.users:
            app.users.remove(session['username'])

        # Send online user count
        emit('online_count', {
            "count": len(app.users),
        }, to='KGBTR')

        # Leave Room
        leave_room('KGBTR')

        disconnect()
    else:
        disconnect()


@app.socketio.on('message')
def handle_json(data=None):
    if 'username' in session:
        if data:
            # MOD Methods
            if session['username'] == 'oldventura':
                if data['message'].startswith('/ban') and (len(data['message'].split()) == 2):
                    ban_username = data['message'].split()[1]
                    if ban_username not in app.blacklist:
                        app.blacklist.append(data['message'].split()[1])
                        emit('incoming', {
                            "type": 'info',
                            "username": "SERVER",
                            "message": f"{ban_username} banned.",
                        }, to='KGBTR')
                        return
                    else:
                        emit('incoming', {
                            "type": 'info',
                            "username": "SERVER",
                            "message": f"{ban_username} is already banned.",
                        }, to='KGBTR')
                        return
            # Normal Procedure
            print(f"{escape(session['username'])}", request.headers.get(
                'X-Forwarded-For', request.remote_addr))
            if not session['last'] or int(time.time()) - int(session['last']) > 5:
                if escape(session['username']) in app.auth:
                    status = 'mod'
                else:
                    status = 'user'

                emit('incoming', {
                    "type": status,
                    "username": escape(session['username']),
                    "message": escape(data['message'][:128]),
                }, to='KGBTR')
                session['last'] = time.time()
    else:
        disconnect()


def reddit_auth(refresh_token=None):
    reddit = praw.Reddit(
        "chatroom",
        refresh_token=refresh_token
    )
    return reddit

# PAGES

# Block banned ip addresses


@app.before_request
def block_method():
    if 'username' in session and session['username'] in app.blacklist:
        abort(403)

@app.route("/")
@limits(calls=_CALLS, period=_PERIOD)
def index():
    if 'username' in session:
        return render_template("index.html", username=session['username'])
    elif 'code' in session:
        try:
            reddit = reddit_auth(session['code'])
            user = reddit.user.me()
            session['username'] = escape(user.name)
            session['last'] = None
            return redirect(app.address+"/")
        except:
            return {"status": "Login failed."}
    else:
        return redirect(app.address+"/login")


@app.route("/logout")
@limits(calls=_CALLS, period=_PERIOD)
def logout():
    if 'username' in session:
        print("disconnectRequest")
        # Remove user from online users
        if session['username'] in app.users:
            app.users.remove(session['username'])

        # Remove username and code from session
        session.pop('username', None)
        session.pop('code', None)
        return redirect(app.address+"/login")
    else:
        return redirect(app.address+"/login")


@app.route("/oauth")
@limits(calls=_CALLS, period=_PERIOD)
def oauth():
    response = request.args
    print(response)
    if 'error' in response:
        return {"status": response['error']}
    elif 'code' in response:
        try:
            reddit = reddit_auth()
            reddit.auth.authorize(response['code'])
            user = reddit.user.me()

            is_subscribed = False
            for sub in reddit.user.subreddits(limit=None):
                if sub.display_name == 'KGBTR':
                    is_subscribed = True
                    break

            if (time.time() - user.created_utc) < (30*24*60*60):
                return {"error": "Account must be at least 1 month old."}, 403
            elif not is_subscribed:
                return {"error": "User is not subscribed to r/KGBTR."}, 403
            else:
                session['code'] = response['code']
                session['username'] = escape(user.name)
                session['last'] = None
                return redirect(app.address+"/")
        except Exception as e:
            print("Exception:", str(e))
            return {"status": "Login failed."}
    else:
        return {"status": "Login failed."}


@app.route("/login", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def login():
    if request.method == 'GET':
        return render_template("login.html")
    else:
        return redirect(app.address+"/login")


@app.route("/reddit_login", methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def reddit_login():
    if request.method == 'GET':
        return redirect(reddit_auth().auth.url(["identity", "mysubreddits"], "login", "permanent"))
    else:
        return redirect(app.address+"/reddit_login")

# Static Content


@app.route('/favicon.svg', methods=["GET"])
@limits(calls=_CALLS, period=_PERIOD)
def favicon():
    return app.send_static_file("images/favicon.svg")
