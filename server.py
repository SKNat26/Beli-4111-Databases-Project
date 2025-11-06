
"""
Columbia's COMS W4111.001 Introduction to Databases
Example Webserver
To run locally:
    python server.py
Go to http://localhost:8111 in your browser.
A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""
import os
# accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, abort, make_response
from datetime import date

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@34.139.8.30/proj1part2
#
# For example, if you had username ab1234 and password 123123, then the following line would be:
#
#     DATABASEURI = "postgresql://ab1234:123123@34.139.8.30/proj1part2"
#
# Modify these with your own credentials you received from TA!
DATABASE_USERNAME = "ay2666"
DATABASE_PASSWRD = "banana2006"
DATABASE_HOST = "34.139.8.30"
DATABASEURI = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWRD}@{DATABASE_HOST}/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#
with engine.connect() as conn:
    create_table_command = """
    CREATE TABLE IF NOT EXISTS test (
        id serial,
        name text
    )
    """
    res = conn.execute(text(create_table_command))
    insert_table_command = """INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace')"""
    res = conn.execute(text(insert_table_command))
    # you need to commit for create, insert, update queries to reflect
    conn.commit()


@app.before_request
def before_request():
    """
    This function is run at the beginning of every web request 
    (every time you enter an address in the web browser).
    We use it to setup a database connection that can be used throughout the request.

    The variable g is globally accessible.
    """
    try:
        g.conn = engine.connect()
    except:
        print("uh oh, problem connecting to database")
        import traceback; traceback.print_exc()
        g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't, the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: https://flask.palletsprojects.com/en/1.1.x/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#
@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments, e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data
    """

    # DEBUG: this is debugging code to see what request looks like
    print(request.args)


    #
    # example of a database query
    #

    user_id = request.cookies.get('user_id')

    if user_id:
        review_query = """
        SELECT 
            u.username AS user, 
            res.name AS restaurant, 
            r.rating AS rating, 
            r.text_content AS text, 
            r.timestamp AS timestamp
        FROM Review r
        LEFT JOIN "User" u
            ON r.user_id = u.user_id
        LEFT JOIN Restaurant res
            ON r.restaurant_id = res.restaurant_id
        ORDER BY timestamp DESC
        """
        cursor = g.conn.execute(text(review_query))
        reviews = []
        for result in cursor:
            reviews.append({
                "user": result[0],
                "restaurant": result[1],
                "rating": result[2],
                "text": result[3],
                "timestamp": result[4]
            })
        cursor.close()

        #
        # Flask uses Jinja templates, which is an extension to HTML where you can
        # pass data to a template and dynamically generate HTML based on the data
        # (you can think of it as simple PHP)
        # documentation: https://realpython.com/primer-on-jinja-templating/
        #
        # You can see an example template in templates/index.html
        #
        # context are the variables that are passed to the template.
        # for example, "data" key in the context variable defined below will be 
        # accessible as a variable in index.html:
        #
        #     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
        #     <div>{{data}}</div>
        #     
        #     # creates a <div> tag for each element in data
        #     # will print: 
        #     #
        #     #   <div>grace hopper</div>
        #     #   <div>alan turing</div>
        #     #   <div>ada lovelace</div>
        #     #
        #     {% for n in data %}
        #     <div>{{n}}</div>
        #     {% endfor %}
        #
        context = dict(data = reviews)


        #
        # render_template looks in the templates/ folder for files.
        # for example, the below file reads template/index.html
        #
        return render_template("index.html", **context, user_id=user_id)
    else:
        return redirect('/login')

#
# This is an example of a different path.  You can see it at:
# 
#     localhost:8111/another
#
# Notice that the function name is another() rather than index()
# The functions for each app.route need to have different names
#
@app.route('/restaurant', methods=['GET'])
def restaurant():
    user_id = request.cookies.get('user_id')

    if user_id:
        search_term = request.args.get('search', '').strip()
        min_rating = request.args.get('rating', '')

        restaurant_query = """
            SELECT 
                r.restaurant_id,
                r.name, 
                r.address, 
                r.cuisine,
                COALESCE(ROUND(AVG(rev.rating)::numeric, 1), 0) as avg_rating,
                COUNT(rev.review_id) as review_count
            FROM Restaurant r
            LEFT JOIN Review rev ON r.restaurant_id = rev.restaurant_id
        """
        
        where_clauses = []
        params = {}
        
        if search_term:
            where_clauses.append("LOWER(r.name) LIKE LOWER(:search)")
            params['search'] = f"%{search_term}%"
        
        if where_clauses:
            restaurant_query += " WHERE " + " AND ".join(where_clauses)
        
        restaurant_query += """
            GROUP BY r.restaurant_id, r.name, r.address, r.cuisine
        """
        
        if min_rating:
            restaurant_query += " HAVING COALESCE(AVG(rev.rating), 0) >= :min_rating"
            params['min_rating'] = float(min_rating)
        
        restaurant_query += " ORDER BY avg_rating DESC, r.name ASC"
        
        cursor = g.conn.execute(text(restaurant_query), params)
        restaurants = []
        for result in cursor:
            restaurants.append({
                "id": result[0],
                "name": result[1],
                "address": result[2],
                "cuisine": result[3],
                "avg_rating": result[4],
                "review_count": result[5]
            })
        cursor.close()

        context = dict(data=restaurants)

        return render_template("restaurant.html", **context)
    else:
        return redirect('/login')


@app.route('/add_restaurant', methods=['GET', 'POST'])
def add_restaurant():
    user_id = request.cookies.get('user_id')

    if user_id:
        message = None

        if request.method == 'POST':
            name = request.form.get('name')
            address = request.form.get('address')
            cuisine = request.form.get('cuisine')

            try:
                insert_restaurant = """
                INSERT INTO Restaurant (name, address, cuisine)
                VALUES (:name, :address, :cuisine)
                """
                g.conn.execute(
                    text(insert_restaurant),
                    {"name": name, "address": address, "cuisine": cuisine})
                g.conn.commit()
                return redirect('/restaurant')
            except Exception as e:
                print(str(e))
                message = f"Restaurant Add Failed: {str(e)}"

        return render_template("add_restaurant.html", message=message)
    else:
        return redirect('/login')

@app.route('/add_review', methods=['GET', 'POST'])
def add_review():
    user_id = request.cookies.get('user_id')

    if user_id:
        restaurant_id = """
            SELECT restaurant_id, name
            FROM Restaurant
        """
        cursor = g.conn.execute(text(restaurant_id))
        restaurants = []
        for result in cursor:
            restaurants.append({
                "id": result[0],
                "name": result[1]
            })
        cursor.close()

        message = None

        context = dict(data = restaurants)

        if request.method == 'POST':
            restaurant_id = request.form.get('restaurant')
            rating = request.form.get('rating')
            text_content = request.form.get('text')

            try:
                insert_review = """
                INSERT INTO Review (restaurant_id, user_id, rating, text_content, "timestamp")
                VALUES (:restaurant_id, :user_id, :rating, :text_content, CURRENT_TIMESTAMP)
                """
                g.conn.execute(text(insert_review), {"restaurant_id": restaurant_id, "user_id": user_id, "rating": rating, "text_content": text_content})
                g.conn.commit()
                return redirect('/')
            except Exception as e:
                print(e)
                message = f'Review Submission Failed: {str(e)}'

        return render_template("add_review.html", **context, message=message)
    else:
        return redirect('/login')

@app.route('/login', methods=["GET", "POST"])
def login():
    message = None

    if request.method == "POST":
        user = request.form.get('username')
        passw = request.form.get('password')

        check_valid_query = """
        SELECT user_id
        FROM "User"
        WHERE username = :user AND password = :passw 
        """

        cursor = g.conn.execute(text(check_valid_query), {"user": user, "passw": passw})
        result = cursor.fetchone()
        cursor.close()

        if result is not None:
            user_id = result[0]
            resp = redirect('/')
            resp.set_cookie('user_id', str(user_id))

            return resp
        else:
            message = "Invalid login"

    return render_template("login.html", message=message)

@app.route('/register', methods=["GET", "POST"])
def register():
    message = None

    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        add_new_user = """
        INSERT INTO "User" (username, email, join_date, password)
        VALUES (:username, :email, :join_date, :password)
        """

        try:
            g.conn.execute(text(add_new_user), {"username":username, "email": email, "join_date": date.today().strftime("%Y-%m-%d"), "password": password})
            g.conn.commit()
            return redirect('/login')
        except Exception as e:
            print(str(e))
            message=f"Registration Failed: {str(e)}"
    return render_template('register.html', message=message)

@app.route('/dishes', methods=['GET'])
def dishes():
    user_id = request.cookies.get('user_id')

    if user_id:
        search_term = request.args.get('search', '').strip()
        restaurant_filter = request.args.get('restaurant', '')
        allergen_exclude = request.args.get('allergen', '')

        dish_query = """
            SELECT DISTINCT
                d.dish_id,
                d.name,
                d.description,
                s.price,
                r.name as restaurant_name,
                r.restaurant_id
            FROM Dish d
            JOIN Serves s ON d.dish_id = s.dish_id
            JOIN Restaurant r ON s.restaurant_id = r.restaurant_id
        """
        
        where_clauses = []
        params = {}
        
        if search_term:
            where_clauses.append("LOWER(d.name) LIKE LOWER(:search)")
            params['search'] = f"%{search_term}%"
        
        if restaurant_filter:
            where_clauses.append("r.restaurant_id = :restaurant_id")
            params['restaurant_id'] = int(restaurant_filter)
        
        if allergen_exclude:
            where_clauses.append("""
                d.dish_id NOT IN (
                    SELECT dish_id 
                    FROM Contains 
                    WHERE allergen_id = :allergen_id
                )
            """)
            params['allergen_id'] = int(allergen_exclude)
        
        if where_clauses:
            dish_query += " WHERE " + " AND ".join(where_clauses)
        
        dish_query += " ORDER BY r.name ASC, d.name ASC"
        
        cursor = g.conn.execute(text(dish_query), params)
        dishes_list = []
        
        for result in cursor:
            dish_id = result[0]
            
            allergen_query = """
                SELECT a.allergen_name
                FROM Contains c
                JOIN Allergens a ON c.allergen_id = a.allergen_id
                WHERE c.dish_id = :dish_id
                ORDER BY a.allergen_name
            """
            allergen_cursor = g.conn.execute(text(allergen_query), {"dish_id": dish_id})
            allergens = [row[0] for row in allergen_cursor]
            allergen_cursor.close()
            
            dishes_list.append({
                "dish_id": result[0],
                "name": result[1],
                "description": result[2],
                "price": result[3],
                "restaurant": result[4],
                "restaurant_id": result[5],
                "allergens": allergens
            })
        cursor.close()

        restaurant_list_query = """
            SELECT DISTINCT restaurant_id, name
            FROM Restaurant
            ORDER BY name
        """
        rest_cursor = g.conn.execute(text(restaurant_list_query))
        restaurants = [{"restaurant_id": row[0], "name": row[1]} for row in rest_cursor]
        rest_cursor.close()

        allergen_list_query = """
            SELECT allergen_id, allergen_name
            FROM Allergens
            ORDER BY allergen_name
        """
        allergen_cursor = g.conn.execute(text(allergen_list_query))
        allergens = [{"allergen_id": row[0], "allergen_name": row[1]} for row in allergen_cursor]
        allergen_cursor.close()

        context = dict(
            data=dishes_list,
            restaurants=restaurants,
            allergens=allergens
        )

        return render_template("dishes.html", **context)
    else:
        return redirect('/login')
    

@app.route('/restaurant/<int:restaurant_id>', methods=['GET'])
def restaurant_info(restaurant_id):
    user_id = request.cookies.get('user_id')

    if user_id:
        restaurant_query = """
            SELECT 
                r.restaurant_id,
                r.name, 
                r.address, 
                r.cuisine,
                COALESCE(ROUND(AVG(rev.rating)::numeric, 1), 0) as avg_rating,
                COUNT(rev.review_id) as review_count
            FROM Restaurant r
            LEFT JOIN Review rev ON r.restaurant_id = rev.restaurant_id
            WHERE r.restaurant_id = :restaurant_id
            GROUP BY r.restaurant_id, r.name, r.address, r.cuisine
        """
        
        cursor = g.conn.execute(text(restaurant_query), {"restaurant_id": restaurant_id})
        result = cursor.fetchone()
        cursor.close()
        
        if not result:
            abort(404)
        
        restaurant = {
            "restaurant_id": result[0],
            "name": result[1],
            "address": result[2],
            "cuisine": result[3],
            "avg_rating": result[4],
            "review_count": result[5]
        }

        dishes_query = """
            SELECT 
                d.dish_id,
                d.name,
                d.description,
                s.price
            FROM Dish d
            JOIN Serves s ON d.dish_id = s.dish_id
            WHERE s.restaurant_id = :restaurant_id
            ORDER BY d.name ASC
        """
        
        cursor = g.conn.execute(text(dishes_query), {"restaurant_id": restaurant_id})
        dishes = []
        
        for result in cursor:
            dish_id = result[0]
            
            allergen_query = """
                SELECT a.allergen_name
                FROM Contains c
                JOIN Allergens a ON c.allergen_id = a.allergen_id
                WHERE c.dish_id = :dish_id
                ORDER BY a.allergen_name
            """
            cursor = g.conn.execute(text(allergen_query), {"dish_id": dish_id})
            allergens = [row[0] for row in cursor]
            cursor.close()

            dishes.append({
                "dish_id": result[0],
                "name": result[1],
                "description": result[2],
                "price": result[3],
                "allergens": allergens
            })
        cursor.close()

        reviews_query = """
            SELECT 
                u.username AS user, 
                r.rating AS rating, 
                r.text_content AS text, 
                r.timestamp AS timestamp
            FROM Review r
            LEFT JOIN "User" u ON r.user_id = u.user_id
            WHERE r.restaurant_id = :restaurant_id
            ORDER BY r.timestamp DESC
        """
        cursor = g.conn.execute(text(reviews_query), {"restaurant_id": restaurant_id})
        reviews = []
        for result in cursor:
            reviews.append({
                "user": result[0],
                "rating": result[1],
                "text": result[2],
                "timestamp": result[3]
            })
        cursor.close()

        context = dict(
            restaurant=restaurant,
            dishes=dishes,
            reviews=reviews
        )

        return render_template("restaurant_info.html", **context)
    else:
        return redirect('/login')
    
@app.route('/add_dish', methods=['GET', 'POST'])
def add_dish():
    user_id = request.cookies.get('user_id')

    if user_id:
        restaurant_query = """
            SELECT restaurant_id, name
            FROM Restaurant
            ORDER BY name
        """
        cursor = g.conn.execute(text(restaurant_query))
        restaurants = []
        for result in cursor:
            restaurants.append({
                "restaurant_id": result[0],
                "name": result[1]
            })
        cursor.close()

        allergen_query = """
            SELECT allergen_id, allergen_name
            FROM Allergens
            ORDER BY allergen_name
        """
        cursor = g.conn.execute(text(allergen_query))
        allergens = []
        for result in cursor:
            allergens.append({
                "allergen_id": result[0],
                "allergen_name": result[1]
            })
        cursor.close()

        message = None

        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            restaurant_id = request.form.get('restaurant')
            price = request.form.get('price')
            selected_allergens = request.form.getlist('allergens')

            try:
                insert_dish = """
                INSERT INTO Dish (name, description)
                VALUES (:name, :description)
                RETURNING dish_id
                """
                result = g.conn.execute(
                    text(insert_dish),
                    {"name": name, "description": description}
                )
                dish_id = result.fetchone()[0]

                insert_serves = """
                INSERT INTO Serves (restaurant_id, dish_id, price)
                VALUES (:restaurant_id, :dish_id, :price)
                """
                g.conn.execute(
                    text(insert_serves),
                    {"restaurant_id": restaurant_id, "dish_id": dish_id, "price": price}
                )

                for allergen_id in selected_allergens:
                    insert_allergen = """
                    INSERT INTO Contains (dish_id, allergen_id)
                    VALUES (:dish_id, :allergen_id)
                    """
                    g.conn.execute(
                        text(insert_allergen),
                        {"dish_id": dish_id, "allergen_id": allergen_id}
                    )

                g.conn.commit()
                return redirect('/dishes')
            except Exception as e:
                print(str(e))
                message = f"Dish Add Failed: {str(e)}"
        
        context = dict(
            restaurants=restaurants,
            allergens=allergens,
            message=message
        )
        
        return render_template("add_dish.html", **context)
    else:
        return redirect('/login')

@app.route('/logout')
def logout():
    resp = make_response(redirect("/login"))
    resp.delete_cookie("user_id")
    return resp

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using:

            python/python3 server.py

        Show the help text using:

            python/python3 server.py --help

        """

        HOST, PORT = host, port
        print("running on %s:%d" % (HOST, PORT))
        app.run(host=HOST, port=PORT, debug=True, threaded=threaded)

run()
