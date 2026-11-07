from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

try:
    from .inclass import (
        AuthenticationError,
        BorrowingClub,
        ValidationError,
        ClubError,
        RequestStatus,
    )
except ImportError:
    from inclass import (
        AuthenticationError,
        BorrowingClub,
        ValidationError,
        ClubError,
        RequestStatus,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
app = Flask(__name__, template_folder=str(FRONTEND_ROOT / "templates"), static_folder=str(FRONTEND_ROOT / "static"))
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "green-view-development-key")

club = BorrowingClub("Green View Hostel")
admin = club.add_administrator("Hostel Warden", "admin", "admin123")
brian = club.register_member("Brian Okello", "brian", "pass1", "A12", "0700000001")
grace = club.register_member("Grace Namukasa", "grace", "pass2", "B05", "0700000002")
simon = club.register_member("Nyabwana Simon Peter", "simon", "pass3", "C07", "0700000003")

calculator = club.add_item(brian, "Electronic", "Scientific Calculator", "Casio scientific calculator", brand="Casio")
iron = club.add_item(brian, "Appliance", "Iron Box", "1200W steam iron", power_watts=1200)
bucket = club.add_item(grace, "Household", "Bucket", "10 litre plastic bucket")
textbook = club.add_item(grace, "Book", "Database Systems", "Database fundamentals textbook", author="Elmasri")
charger = club.add_item(grace, "Electronic", "Phone Charger", "Fast USB-C charger", brand="Samsung")

# Additional inventory and sample borrowing activity.
lamp = club.add_item(brian, "Household", "Study Lamp", "Adjustable LED desk lamp")
blender = club.add_item(grace, "Appliance", "Blender", "Compact kitchen blender", power_watts=750)
novel = club.add_item(simon, "Book", "The River Between", "Ngugi wa Thiong'o novel", author="Ngugi wa Thiong'o")
extension = club.add_item(simon, "Electronic", "Extension Cable", "Four-socket extension cable", brand="Generic")
heater = club.add_item(grace, "Appliance", "Room Heater", "Energy-efficient room heater", power_watts=1600)
chair = club.add_item(brian, "Household", "Study Chair", "Comfortable wooden study chair")
headphones = club.add_item(simon, "Electronic", "Headphones", "Wireless over-ear headphones", brand="Sony")
math_book = club.add_item(brian, "Book", "Engineering Mathematics", "Volume one mathematics textbook", author="K. A. Stroud")

club.request_item(simon, charger, date.today() - timedelta(days=2))
club.approve_request(grace, club.full_history()[0], 4)
club.borrow_item(simon, club.full_history()[0], date.today() - timedelta(days=2))

camera_request = club.request_item(brian, headphones, date.today() - timedelta(days=1))
club.approve_request(simon, camera_request, 4)
club.borrow_item(brian, camera_request, date.today() - timedelta(days=1))

club.request_item(simon, heater, date.today())


def current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return next((user for user in club._BorrowingClub__admins + club._BorrowingClub__members if user.user_id == user_id), None)


def user_by_id(user_id: int):
    return next((user for user in club._BorrowingClub__admins + club._BorrowingClub__members if user.user_id == user_id), None)


def item_by_id(item_id: int):
    return next((item for item in club.all_items() if item.item_id == item_id), None)


def request_by_id(request_id: int):
    return next((borrowing_request for borrowing_request in club.full_history() if borrowing_request.request_id == request_id), None)


def require_login():
    user = current_user()
    if user is None:
        return None, (jsonify({"error": "Please sign in."}), 401)
    return user, None


def serialize_item(item):
    return {
        "id": item.item_id,
        "name": item.name,
        "description": item.description,
        "category": item.CATEGORY,
        "owner": item.owner.name,
        "ownerId": item.owner.user_id,
        "status": item.status.value,
        "available": item.is_available(),
        "maxDays": item.max_borrow_days,
        "penaltyPerDay": item.penalty_per_day,
    }


def serialize_request(borrowing_request):
    return {
        "id": borrowing_request.request_id,
        "itemId": borrowing_request.item.item_id,
        "itemName": borrowing_request.item.name,
        "borrowerId": borrowing_request.borrower.user_id,
        "borrowerName": borrowing_request.borrower.name,
        "ownerName": borrowing_request.item.owner.name,
        "status": borrowing_request.status.value,
        "borrowDate": borrowing_request.borrow_date.isoformat() if borrowing_request.borrow_date else None,
        "dueDate": borrowing_request.due_date.isoformat() if borrowing_request.due_date else None,
        "returnDate": borrowing_request.return_date.isoformat() if borrowing_request.return_date else None,
        "daysOverdue": borrowing_request.days_overdue(),
        "penalty": borrowing_request.penalty(),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or request.form
    try:
        user = club.login(data.get("username", ""), data.get("password", ""))
        session["user_id"] = user.user_id
        return jsonify({
            "user": {
                "id": user.user_id,
                "name": user.name,
                "username": user.username,
                "role": user.role.value,
                "isAdmin": user.role.value == "Administrator",
            }
        })
    except (AuthenticationError, ClubError) as error:
        return jsonify({"error": str(error)}), 401


@app.post("/api/logout")
def logout():
    club.logout()
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/session")
def session_info():
    user = current_user()
    if user is None:
        return jsonify({"user": None})
    return jsonify({
        "user": {
            "id": user.user_id,
            "name": user.name,
            "username": user.username,
            "role": user.role.value,
            "isAdmin": user.role.value == "Administrator",
        }
    })


@app.get("/api/dashboard")
def dashboard():
    user, error = require_login()
    if error:
        return error

    items = club.all_items()
    requests = club.full_history() if user.role.value == "Administrator" else club.history_for(user)
    club.check_overdue()
    member_activity = []
    if user.role.value == "Administrator":
        for member in club._BorrowingClub__members:
            borrowing = [borrow for borrow in club.full_history() if borrow.borrower == member]
            lending = [borrow for borrow in club.full_history() if borrow.item.owner == member]
            member_activity.append({
                "id": member.user_id,
                "name": member.name,
                "username": member.username,
                "room": member.room_number,
                "itemsListed": len(member.items),
                "borrowedCount": sum(borrow.status in (RequestStatus.BORROWED, RequestStatus.OVERDUE) for borrow in borrowing),
                "requestsCount": len(borrowing),
                "lendingCount": len(lending),
                "overdueCount": sum(borrow.update_overdue() for borrow in borrowing),
                "activity": [serialize_request(borrow) for borrow in (borrowing + lending)],
            })

    profile = {
        "id": user.user_id,
        "name": user.name,
        "username": user.username,
        "role": user.role.value,
        "room": getattr(user, "room_number", None),
        "phone": getattr(user, "phone", None),
        "itemsListed": len(user.items) if hasattr(user, "items") else 0,
    }
    return jsonify({
        "profile": profile,
        "memberActivity": member_activity,
        "history": [serialize_request(borrowing_request) for borrowing_request in requests],
        "items": [serialize_item(item) for item in items],
        "availableItems": [serialize_item(item) for item in club.available_items()],
        "requests": [serialize_request(borrowing_request) for borrowing_request in requests],
        "pendingRequests": [serialize_request(borrowing_request) for borrowing_request in club.pending_requests_for(user)] if user.role.value != "Administrator" else [],
        "members": [
            {
                "id": member.user_id,
                "name": member.name,
                "username": member.username,
                "room": member.room_number,
                "phone": member.phone,
                "items": len(member.items),
            }
            for member in club._BorrowingClub__members
        ],
        "stats": {
            "items": len(items),
            "available": len(club.available_items()),
            "borrowed": len(club.currently_borrowed()),
            "requests": len(requests),
            "overdue": len(club.check_overdue()),
        },
    })


@app.post("/api/items")
def create_item():
    user, error = require_login()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        extras = {}
        if data.get("category", "").lower() == "electronic":
            extras["brand"] = data.get("detail", "Generic")
        elif data.get("category", "").lower() == "appliance":
            extras["power_watts"] = max(0, int(data.get("detail", 0) or 0))
        elif data.get("category", "").lower() == "book":
            extras["author"] = data.get("detail", "Unknown")
        item = club.add_item(user, data.get("category", ""), data.get("name", ""), data.get("description", ""), **extras)
        return jsonify({"item": serialize_item(item)}), 201
    except (ClubError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id: int):
    user, error = require_login()
    if error:
        return error
    item = item_by_id(item_id)
    if item is None:
        return jsonify({"error": "Item not found."}), 404
    if not user.role.value == "Administrator" and item.owner != user:
        return jsonify({"error": "Only the item owner can delete this item."}), 403
    if not item.is_available():
        return jsonify({"error": "Items on loan cannot be deleted."}), 400
    if any(borrowing_request.item == item for borrowing_request in club.full_history()):
        return jsonify({"error": "Items with borrowing history cannot be deleted."}), 400
    owner_items = item.owner._ClubMember__items
    owner_items.remove(item)
    return jsonify({"ok": True})


@app.put("/api/profile")
def update_profile():
    user, error = require_login()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", user.username)).strip().lower()
    try:
        if username != user.username and any(
            account.username == username
            for account in (*club._BorrowingClub__admins, *club._BorrowingClub__members)
        ):
            raise ValidationError(f"Username '{username}' is already taken.")
        user.update_profile(str(data.get("name", user.name)), username)
        if user.role.value == "Club Member":
            user.room_number = str(data.get("room", user.room_number)).strip()
            user.phone = str(data.get("phone", user.phone)).strip()
        password = str(data.get("password", "")).strip()
        if password:
            user.reset_password(password)
        return jsonify({"profile": {
            "id": user.user_id,
            "name": user.name,
            "username": user.username,
            "role": user.role.value,
        }})
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/members")
def create_member():
    user, error = require_login()
    if error:
        return error
    if user.role.value != "Administrator":
        return jsonify({"error": "Only an administrator can register members."}), 403
    data = request.get_json(silent=True) or {}
    try:
        member = club.register_member(
            data.get("name", ""), data.get("username", ""), data.get("password", ""),
            data.get("room", ""), data.get("phone", ""),
        )
        return jsonify({"member": {"id": member.user_id, "name": member.name, "username": member.username}}), 201
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/requests")
def create_request():
    user, error = require_login()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    item = item_by_id(int(data.get("itemId", 0)))
    if item is None:
        return jsonify({"error": "Item not found."}), 404
    try:
        borrowing_request = club.request_item(user, item)
        return jsonify({"request": serialize_request(borrowing_request)}), 201
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/requests/<int:request_id>/approve")
def approve_request(request_id: int):
    user, error = require_login()
    if error:
        return error
    borrowing_request = request_by_id(request_id)
    if borrowing_request is None:
        return jsonify({"error": "Request not found."}), 404
    data = request.get_json(silent=True) or {}
    try:
        club.approve_request(user, borrowing_request, int(data.get("days", 4)))
        return jsonify({"request": serialize_request(borrowing_request)})
    except (ClubError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/requests/<int:request_id>/reject")
def reject_request(request_id: int):
    user, error = require_login()
    if error:
        return error
    borrowing_request = request_by_id(request_id)
    if borrowing_request is None:
        return jsonify({"error": "Request not found."}), 404
    try:
        club.reject_request(user, borrowing_request)
        return jsonify({"request": serialize_request(borrowing_request)})
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/requests/<int:request_id>/collect")
def collect_request(request_id: int):
    user, error = require_login()
    if error:
        return error
    borrowing_request = request_by_id(request_id)
    if borrowing_request is None:
        return jsonify({"error": "Request not found."}), 404
    try:
        club.borrow_item(user, borrowing_request)
        return jsonify({"request": serialize_request(borrowing_request)})
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/requests/<int:request_id>/return")
def return_request(request_id: int):
    user, error = require_login()
    if error:
        return error
    borrowing_request = request_by_id(request_id)
    if borrowing_request is None:
        return jsonify({"error": "Request not found."}), 404
    try:
        club.return_item(user, borrowing_request)
        return jsonify({"request": serialize_request(borrowing_request)})
    except ClubError as error:
        return jsonify({"error": str(error)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
