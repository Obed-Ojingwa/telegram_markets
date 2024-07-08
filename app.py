from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import random
import atexit

from models import db, Player, Asset, Transaction

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///game.db'
db.init_app(app)
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    players = Player.query.all()
    assets = Asset.query.all()
    return render_template('dashboard.html', players=players, assets=assets)

@app.route('/leaderboard')
def leaderboard():
    players = Player.query.order_by(Player.balance.desc()).all()
    return render_template('leaderboard.html', players=players)

@app.route('/buy', methods=['POST'])
def buy_stock():
    data = request.json
    player = Player.query.get(data['player_id'])
    asset = Asset.query.get(data['asset_id'])
    amount = data['amount']
    cost = amount * asset.price * 1.01

    if player.balance >= cost:
        player.balance -= cost
        transaction = Transaction(player_id=player.id, asset_id=asset.id, amount=amount, type='buy')
        db.session.add(transaction)
        db.session.commit()
        return jsonify({'success': True, 'balance': player.balance})
    else:
        return jsonify({'success': False, 'message': 'Insufficient balance'})

@app.route('/sell', methods=['POST'])
def sell_stock():
    data = request.json
    player = Player.query.get(data['player_id'])
    asset = Asset.query.get(data['asset_id'])
    amount = data['amount']
    revenue = amount * asset.price * 0.99

    player.balance += revenue
    transaction = Transaction(player_id=player.id, asset_id=asset.id, amount=-amount, type='sell')
    db.session.add(transaction)
    db.session.commit()
    return jsonify({'success': True, 'balance': player.balance})

@socketio.on('market_update')
def handle_market_update():
    assets = Asset.query.all()
    for asset in assets:
        change = random.uniform(-0.05, 0.05)
        asset.price = max(0.01, asset.price * (1 + change))
    db.session.commit()
    emit('update', {'assets': [(asset.symbol, asset.price) for asset in assets]}, broadcast=True)

from apscheduler.schedulers.background import BackgroundScheduler

def update_market():
    with app.app_context():
        assets = Asset.query.all()
        for asset in assets:
            change = random.uniform(-0.05, 0.05)
            asset.price = max(0.01, asset.price * (1 + change))
        db.session.commit()
        socketio.emit('update', {'assets': [(asset.symbol, asset.price) for asset in assets]}, broadcast=True)

scheduler = BackgroundScheduler()
scheduler.add_job(func=update_market, trigger="interval", seconds=60)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
