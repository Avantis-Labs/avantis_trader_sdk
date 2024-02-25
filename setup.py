from setuptools import setup, find_packages

setup(
    name='avantis_trader_sdk',
    version='0.1.0',
    author='Avantis Labs',
    author_email='admin@avantisfi.com',
    description='SDK for interacting with Avantis trading contracts.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://avantisfi.com/',
    packages=find_packages(),  
    install_requires=[
        'web3>=6.15.1',
        'pydantic>=1.10.2'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',  # Choose the appropriate license after discussing with brank
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',  
    include_package_data=True,
    package_data={
        '': ['*.txt', '*.rst', '*.json'],
        'hello': ['*.msg'],
    },
    keywords="trading sdk blockchain ethereum web3 avantis",
    license="MIT", # Choose the appropriate license after discussing with brank
)
