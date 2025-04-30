## Getting Started

First install the dependencies on your virtual environment:

1. `pip install -r requirements.txt`

Once the installation is complete, excute:

2. `fastapi run main.py`

## Backend functions

Powered by FastApi, contains the functions to validate a XML file with 3 different schemas:

1. *DTD* -> Defines the order that the XML file could fulfill
2. *XSD* -> Defines the content that the XML file could fulfill
3. *OWL* -> Gives a syntactic value to the XML file

It also allows download a XML file with diferents elements, previously selected by an user on the **frontend** 
