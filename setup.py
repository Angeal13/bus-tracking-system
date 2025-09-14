from setuptools import setup, find_packages

setup(
    name="bus-tracking-system",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pygame>=2.5.2",
        "pyttsx3>=2.90",
        "gTTS>=2.3.2",
        "mariadb>=1.1.8",
        "boto3>=1.34.62",
        "keyboard>=0.13.5",
        "pytz>=2024.1",
        "requests>=2.31.0"
    ],
    entry_points={
        'console_scripts': [
            'bus-tracker=src.main:main',
        ],
    },
)
