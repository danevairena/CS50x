import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get current user id from session
    user_id = session["user_id"]
    # get user's cash  balance from db
    rows = db.execute(
        "SELECT cash FROM users WHERE id = ?", user_id
    )
    cash = rows[0]["cash"]
    # get user's current positions from db
    positions = db.execute(
        "SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id
    )
    # list of holdings to render in index.html
    holdings = []
    # total value of all stocks
    stocks_total = 0
    # for each symbol lookup it's price and calculate total value
    for position in positions:
        symbol = position["symbol"]
        shares = position["total_shares"]
        # lookup returns dict
        stock = lookup(symbol)
        price = stock["price"]

        total = shares * price
        stocks_total += total
        # add row for the template
        holdings.append({"symbol": symbol, "shares": shares, "price": price, "total": total})
    # grand_total is sum of cash and value of stocks
    grand_total = cash + stocks_total

    return render_template("index.html", holdings=holdings, cash=cash, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # if method is GET show buy form
    if request.method == "GET":
        return render_template("buy.html")
    # if method is post proceed the purchase
    elif request.method == "POST":
        # get symbol and shares from form
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # validate symbol input
        if not symbol:
            return apology("Must provide symbol", 400)
        # lookup the symbol to validate it and get current price
        stock = lookup(symbol)
        if stock == None:
            return apology("Invalid symbol", 400)
        # validate shares input
        if not shares:
            return apology("Must provide number of shares", 400)
        # validate shares is positive integer
        try:
            shares_int = int(shares)
            if shares_int <= 0:
                return apology("Shares must be positive number", 400)
        except ValueError:
            return apology("Shares must be positive number", 400)
        # calculate total cost
        price = stock["price"]
        total = price * shares_int
        # get user's current cash
        row = db.execute(
            "SELECT cash FROM users WHERE id = ?", session["user_id"]
        )
        cash = row[0]["cash"]
        # ensure user can afford the purchase
        if total > cash:
            return apology("Can't afford", 400)
        # insert transaction into transactions table
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", session["user_id"], symbol.upper(
            ), shares_int, price
        )
        # update user's balance
        new_cash = cash - total
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"]
        )
        # redirect to homepage after successful purchase
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get current user id from session
    user_id = session["user_id"]
    # get all user's transactions and order by date
    transactions = db.execute(
        "SELECT symbol, shares, price, transacted FROM transactions where user_id = ? ORDER BY transacted DESC", user_id
    )
    # render template with transactions
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/profile", methods=["GET"])
@login_required
def profile():
    # get user from session
    user_id = session["user_id"]
    # query the db to get user's details
    user_data = db.execute(
        "SELECT username, cash FROM users WHERE id = ?", user_id
    )
    username = user_data[0]["username"]
    cash = user_data[0]["cash"]
    # get last 5 transactions
    transactions = db.execute(
        "SELECT symbol, shares, price, transacted FROM transactions WHERE user_id = ? ORDER BY transacted DESC LIMIT 5", user_id
    )
    # render profile template with user details
    return render_template("profile.html", username=username, cash=cash, transactions=transactions)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # if method is GET show quote form
    if request.method == "GET":
        return render_template("quote.html")
    # if methos is POST hande quore request
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        # validate symbol
        if not symbol:
            return apology("Must provide symbol", 400)
        # lookup symbol
        stock = lookup(symbol)
        if stock == None:
            return apology("Invalid symbol", 400)
        # render quoted.html with the stock info
        return render_template("quoted.html", stock=stock)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # if GET request show register form
    if request.method == "GET":
        return render_template("register.html")
    # if POST request create new account
    elif request.method == "POST":
        # validate all fields exist
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("All fields are required", 400)
        # validate password confirmation
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("Password not matching", 400)

        password = request.form.get("password")
        username = request.form.get("username")
        # password hash before storing it
        password_hash = generate_password_hash(password)
        # insert into db
        try:
            new_id = db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)", username, password_hash
            )
        except ValueError:
            # username is unique in db, send error if insertion fails
            return apology("Username already exists", 400)
        # log in the new user and redirect to homepage
        session["user_id"] = new_id
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # if GET request show sale form
    if request.method == "GET":
        user_id = session["user_id"]
        # get symbols that logged user currently owns
        stocks = db.execute(
            "SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0", user_id
        )
        # render sell page with the list of owned stocks
        return render_template("sell.html", stocks=stocks)
    # if POST request process sale
    elif request.method == "POST":
        user_id = session["user_id"]
        # get inputs from form
        symbol = request.form.get("symbol")
        # keep symbol consistent (uppercase)
        symbol = symbol.upper()
        shares_str = request.form.get("shares")
        # validate selected symbol
        if not symbol:
            return apology("You should choose stock to sell", 403)
        # validate shares is positive integer
        try:
            shares = int(shares_str)
        except (TypeError, ValueError):
            return apology("Number of shares to sell not correct", 400)
        if shares <= 0:
            return apology("Number of shares to sell not correct", 400)
        # check how many shares user owns of this symbol
        rows = db.execute(
            "SELECT COALESCE(SUM(shares), 0) AS total_shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol
        )
        owned = rows[0]["total_shares"]
        # if user doesn't own the stock send error
        if owned <= 0:
            return apology("You don't own any shares of that stock", 400)
        # if user tries to sell more than owned send error
        if shares > owned:
            return apology("You don't own that many shares", 400)
        # get stock's current price
        quote = lookup(symbol)
        if quote is None:
            return apology("Invalid symbol", 400)
        price = quote["price"]
        # how much user's recieve from selling
        proceeds = price * shares
        # insert sale transaction
        # negative shares means sell
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)", user_id, symbol, -shares, price
        )
        # update user's cash
        db.execute(
            "UPDATE users SET cash = cash + ? WHERE id = ?", proceeds, user_id
        )
        return redirect("/")
