from . import app
import os
import json
import pymongo
from flask import jsonify, request, make_response, abort, url_for  # noqa: F401
from pymongo import MongoClient
from bson import json_util
from pymongo.errors import OperationFailure
from pymongo.results import InsertOneResult
from bson.objectid import ObjectId
import sys

SITE_ROOT = os.path.realpath(os.path.dirname(__file__))
json_url = os.path.join(SITE_ROOT, "data", "songs.json")
songs_list: list = json.load(open(json_url))

# MongoDB configuration
mongodb_service = os.environ.get('MONGODB_SERVICE')
mongodb_username = os.environ.get('MONGODB_USERNAME')
mongodb_password = os.environ.get('MONGODB_PASSWORD')
mongodb_port = os.environ.get('MONGODB_PORT')

print(f'The value of MONGODB_SERVICE is: {mongodb_service}')

if mongodb_service is None:
    app.logger.error(
        'Missing MongoDB server in the MONGODB_SERVICE variable'
    )
    sys.exit(1)

if mongodb_username and mongodb_password:
    url = f"mongodb://{mongodb_username}:{mongodb_password}@{mongodb_service}"
else:
    url = f"mongodb://{mongodb_service}"

print(f"connecting to url: {url}")

try:
    client = MongoClient(url)
except OperationFailure as e:
    app.logger.error(f"Authentication error: {str(e)}")

db = client.songs

# Load initial songs
db.songs.drop()
db.songs.insert_many(songs_list)


def parse_json(data):
    return json.loads(json_util.dumps(data))


# ------------------------------------------------------------
# HEALTH
# ------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="OK"), 200


# ------------------------------------------------------------
# COUNT
# ------------------------------------------------------------

@app.route("/count", methods=["GET"])
def count():
    """Return the number of songs."""
    count = db.songs.count_documents({})

    return {"count": count}, 200


# ------------------------------------------------------------
# CREATE - POST
# ------------------------------------------------------------

@app.route("/song", methods=["POST"])
def create_song():
    """Create a new song."""

    song_data = request.get_json()

    if not song_data:
        return {"message": "song data required"}, 400

    # Check whether a song with this id already exists
    if "id" in song_data:
        existing_song = db.songs.find_one({"id": song_data["id"]})

        if existing_song is not None:
            return {
                "message": f"song with id {song_data['id']} already present"
            }, 302

    result = db.songs.insert_one(song_data)

    song = db.songs.find_one({"_id": result.inserted_id})

    return parse_json(song), 201


# ------------------------------------------------------------
# READ - GET ALL
# ------------------------------------------------------------

@app.route("/song", methods=["GET"])
def songs():
    """Return all songs from the database."""

    songs_list = db.songs.find({})

    return {
        "songs": parse_json(list(songs_list))
    }, 200


# ------------------------------------------------------------
# READ - GET BY ID
# ------------------------------------------------------------

@app.route("/song/<int:id>", methods=["GET"])
def get_song_by_id(id):
    """Return a song by id."""

    song = db.songs.find_one({"id": id})

    if song is None:
        return {"message": "song with id not found"}, 404

    return parse_json(song), 200


# ------------------------------------------------------------
# UPDATE - PUT
# ------------------------------------------------------------

@app.route("/song/<int:id>", methods=["PUT"])
def update_song(id):
    """Update a song by id."""

    song_data = request.get_json()

    song = db.songs.find_one({"id": id})

    if song is None:
        return {"message": "song not found"}, 404

    # Don't allow the URL id to be changed
    song_data["id"] = id

    db.songs.update_one(
        {"id": id},
        {"$set": song_data}
    )

    updated_song = db.songs.find_one({"id": id})

    return parse_json(updated_song), 200


# ------------------------------------------------------------
# DELETE - DELETE
# ------------------------------------------------------------

@app.route("/song/<int:id>", methods=["DELETE"])
def delete_song(id):
    """Delete a song by id."""

    result = db.songs.delete_one({"id": id})

    if result.deleted_count == 0:
        return {"message": "song not found"}, 404

    return "", 204