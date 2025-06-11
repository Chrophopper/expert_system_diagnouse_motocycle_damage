from flask import Flask
from models import db, populate_db, User
from config import Config
from routes import bp as main_bp
from flask_login import LoginManager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()
        populate_db()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)