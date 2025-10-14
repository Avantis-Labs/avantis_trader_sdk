from setuptools import setup, find_packages

setup(
    name="avantis_trader_sdk",
    version="0.8.9",
    author="Avantis Labs",
    author_email="yug@avantisfi.com",
    description="SDK for interacting with Avantis trading contracts.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://avantisfi.com/",
    packages=find_packages(),
    install_requires=[
        "web3>=6.15.1,<7",
        "pydantic>=2.8.2,<3",
        "websockets>=12.0,<14",
        "boto3>=1.35.44,<2",
        "eth_account>=0.10.0,<0.14",
        "toolz>=0.12.1,<1",
        "eth_utils>=2.1.0,<5",
        "pyasn1>=0.6.1,<1",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    include_package_data=True,
    package_data={
        "": ["*.txt", "*.rst", "*.json"],
        "avantis_trader_sdk": [
            "abis/*.json",
            "abis/*/*.json",
            "abis/*/*/*.json",
        ],
    },
    keywords="trading sdk blockchain ethereum web3 avantis",
    license="MIT",
)
