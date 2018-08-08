import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # remember user
    user = session["user_id"]

    # get symbols and number of shares
    stocks = db.execute("""
                        SELECT symbol, SUM(shares_purchased) - SUM(shares_sold) AS shares
                        FROM transactions
                        WHERE user_id = :user
                        GROUP BY symbol
                        ORDER BY symbol""",
                        user=user)
    # prepare to calculate shares
    total_shares = 0

    for stock in stocks:
        # get price of individual shares by looking up the symbol and then storing the price from the value returned
        symbol = lookup(stock["symbol"])
        price = symbol["price"]


        # claculate total value of shares
        value = round(price * stock["shares"],2)

        # calculate total shares
        total_shares += value

        # update stock dictionary
        stock.update({"price": price, "value": value})

    # get cash amount
    cash = db.execute("SELECT cash FROM users WHERE id = :user", user=user)
    cash = cash[0]["cash"]

    # get money total
    total = cash + total_shares

    # render table
    return render_template("index.html", stocks=stocks, total_shares=total_shares, cash=cash, total=total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # make sure symbol was provided
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Symbol and shares required")

        # make sure symbol is valid and shares are a positive int
        symbol = lookup(request.form.get("symbol"))
        shares = request.form.get("shares")
        if not symbol or "." in shares or int(shares) < 1:
            return apology("Invalid symbol or shares number")


        # calculate cost
        shares = int(shares)
        price = int(symbol["price"]) * shares
        return render_template("test.html", result=price)


        # check if user has enugh funds
        user = session["user_id"]

        row = db.execute("SELECT cash FROM users WHERE id = :user", user=user)
        cash = row[0]["cash"]

        if cash < price:
            return apology("Not enough funds")

        # update user's cash
        cash -=price
        db.execute("UPDATE users SET cash = :cash WHERE id = :user", cash=cash, user=user)

        # record purchase
        db.execute("""
                    INSERT INTO transactions(user_id, symbol, shares_purchased, price, date)
                    VALUES (:user, :symbol, :shares, :price, datetime('now'))""",
                    user=user, symbol=symbol["symbol"], shares=shares, price=price)

        # show portfolio
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # make sure symbol was provided
        if not request.form.get("symbol"):
            return apology("Symbol required")

        # use lookup to get quote
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        # verify that a quite was returned
        if not quote:
            return apology("Invalid symbol")

        # render quote
        return render_template("quoted.html", symbol=quote["symbol"], price=quote["price"])

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted and that it does not exist
        if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Missing fields!", 403)
        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

        # remember username entry
        username = request.form.get("username")

        # hash the password
        hash = generate_password_hash(request.form.get("password"))

        # insert username and password into data base
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)

        # if the user name is not unique, execute will fail
        if not result:
            return apology("username already exists", 403)

        # log in user by rembering id and redirecting to home page
        user_id = db.execute("SELECT id FROM users WHERE username = :username", username=username)
        session["user_id"] = user_id
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # make sure symbol was provided
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("Symbol and shares required")

        # make sure symbol is valid and shares are a positive int
        symbol_values = lookup(request.form.get("symbol"))
        shares = request.form.get("shares")
        if not symbol_values or "." in shares or int(shares) < 1:
            return apology("Invalid symbol or shares number")

        # check if user has enugh shares
        user = session["user_id"]
        shares = int(shares)
        symbol = symbol_values["symbol"]

        row = db.execute("""
                        SELECT SUM(shares_purchased) - SUM(shares_sold) AS shares
                        FROM transactions
                        WHERE user_id = :user AND symbol = :symbol""",
                        user=user, symbol=symbol)
        user_shares = row[0]["shares"]

        if user_shares < shares:
            return apology("Not enough shares")

        # update user's cash
        price = int (symbol_values["price"]) * shares
        result = db.execute("UPDATE users SET cash = cash + :price WHERE id = :user", price=price, user=user)


        # record sale
        db.execute("""
                    INSERT INTO transactions (user_id, symbol, shares_sold, price, date)
                    VALUES (:user, :symbol,:shares, :price, datetime('now'))""",
                    user=user, symbol=symbol, shares=shares, price=price)

        # show portfolio
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
