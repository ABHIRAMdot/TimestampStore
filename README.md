⌚ TimeStamp Store

TimeStamp Store is an e-commerce web application where users can browse and purchase premium quality watches at affordable prices.
This is my first project built using Python Django as part of my learning journey into web development.

Features

Browse premium watches

View product details and pricing

Clean and user-friendly interface

Backend built using Django

Django Admin panel for product management

Future expansion planned for cart & order system

🛠 Tech Stack

Backend: Python, Django

Frontend: HTML, Tailwind CSS

Database: PostgreSQL

Admin Panel: Django Admin

⚙️ Installation & Setup

Follow the steps below to run the project locally:

1️. Clone the Repository
git clone https://github.com/your-username/timestamp-store.git

2️. Navigate to the Project Directory
cd timestamp-store

3️. Create a Virtual Environment (Recommended)
python -m venv venv

4️. Activate the Virtual Environment

Windows

venv\Scripts\activate


Mac / Linux

source venv/bin/activate

5️. Install Dependencies
pip install -r requirements.txt

6️. Configure Database

Update PostgreSQL credentials in settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'timestamp_db',
        'USER': 'postgres',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

7️. Run Migrations
python manage.py makemigrations
python manage.py migrate

8️. Create Superuser (Admin Access)
python manage.py createsuperuser

9️. Start the Development Server
python manage.py runserver

10. Open in Browser
http://127.0.0.1:8000/


Admin Panel:

http://127.0.0.1:8000/admin/

🚀 Usage

Browse available watches on the homepage

Click on products to view details

Manage products and users via /admin

Admin can add/edit/delete products

📁 Project Structure (Basic)
timestamp-store/
│── manage.py
│── requirements.txt
│── timestamp_store/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│── products/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│── templates/
│── static/

👤 Author

Created by Abhiram

📍 Project Status

Under Development – This is my first Django project

Planned Improvements:

Better UI design

Shopping cart functionality

Order & checkout system

Payment gateway integration