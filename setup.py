from setuptools import setup

setup(
    name = 'bitcallback',
    version = '0.1',
   
    # Info
    description = 'Bitcoin monitoring and notification RESTful service',
    url = 'https://github.com/secnot/bitcoin-callback',
    author = 'secnot',
    keywords = ['bitcoin', 'callback'],

    # Package
    packages=['bitcallback'],
    include_package_data=True,
    install_requires=[
        'flask',
        'flask-restplus',
        'Flask-SQLAlchemy',
        'python-swagger-ui',

        #
        'multiprocessing-logging',
        'SQLAlchemy',
        'requests',
        'python-bitcoinlib',

        #
        'unittest2',
        'nose',
    ],

    # Tests
    test_suite='nose.collector',
    test_require=['nose'],
)
