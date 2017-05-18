import xml.etree.cElementTree as ET
import pprint
import re
import codecs
import json
from collections import defaultdict

#find the two-level values 
lower_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')

#find the three-level values 
lower_double_colon = re.compile(r'^([a-z]|_)*:([a-z]|_)*:([a-z]|_)*$')

#find the problamatic values 
problemchars = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

#valid country  
canada = re.compile(r'^(CA)$')

#valid province
ontario = re.compile(r'^(ON)$')

#other province values to be converted to "ON"
ontario_alternative = ["Ontario", "ontario","On", "on", "Onatrio"]

#valid cities
city = re.compile(r'^(Toronto|York|North York|East York)$')

#other toronto values to be converted to "Toronto"
toronto_alternative = ["CityofToronto", "City of Toronto", "Toronto,ON", "Torontoitalian"]

#other North York values to be converted to "North York"
northyork_alternative = ["NorthYork"]

#other East York values to be converted to "East York"
eastyork_alternative = ["EastYork"]

#valid postal code format
postcode = re.compile(r'^([A-Z][0-9][A-Z][ ][0-9][A-Z][0-9])$')

#other postal code format to be converted to the valid one
postcode_alternative = re.compile(r'^([A-Z][0-9][A-Z][0-9][A-Z][0-9])$')

#any type of abbreviation
street = re.compile(r'\b([a-z]|_)*\.', re.IGNORECASE)

#Created object 
CREATED = [ "version", "changeset", "timestamp", "user", "uid"]

#Position object
POSITION = [ "lat", "lon"]

#valid names to come after St.
SAINTS = ["Andrew's", "Edmund's", "John's", "Leonard's", "George", "Clair", "Helens", "Dennis", "Joseph", "Clarens",
          "Matthews", "Hubert", "James", "David", "Thomas", "Mary", "Patrick", "Clements", "Leonards", "Hildas", "Mathias",
          "Andrews", "Raymond", "Annes", "Cuthberts", "Cuthberts", "Ives", "Edmunds"]

#dictionary of all problamtic items by category
problematic_elements = {}
problematic_elements["key_invalid_char"] = []
problematic_elements["key_double_colon"] = []
problematic_elements["country"] = []
problematic_elements["province"] = []
problematic_elements["city"] = []
problematic_elements["street"] = []
problematic_elements["postcode"] = []

#create json object based on element
def shape_element(element):
    node = {}
    if element.tag == "node" or element.tag == "way" :
        node["id"] = element.attrib["id"]
        node["type"] = element.tag
        for key,value in element.attrib.iteritems():
            if key in CREATED:
                if 'created' not in node:
                    node['created'] = {}
                node["created"][key] = value
            elif key in POSITION:
                if 'pos' not in node:
                    node['pos'] = [None]*2
                if key == 'lat':
                    node["pos"][0] = float(value)
                elif key == 'lon':
                    node["pos"][1] = float(value)
            else:
                node[key] = value
            
        for tag in element.iter():
            if tag.tag == 'tag':
                tag_key = tag.attrib["k"]
                if is_match(problemchars, tag_key):
                    problematic_elements["key_invalid_char"].append(tag_key)
                    continue
                if is_match(lower_double_colon , tag_key):
                    problematic_elements["key_double_colon"].append(tag_key)
                    continue
                if is_match(lower_colon , tag_key):
                    parse_colon(node, tag, tag_key)
                else:
                    is_valid_value,final_value = check_value(tag_key, tag.attrib['v'])
                    if is_valid_value:
                        node[tag_key] = final_value
            elif tag.tag == 'nd':
                if 'node_refs' not in node:
                    node['node_refs'] = []
                node['node_refs'].append(tag.attrib['ref'])
       
        return node
    else:
        return None

# create two level objects like address
def parse_colon(node, element, tag_key):
    key_part_1,key_part_2 = tag_key.split(':')
    if key_part_1 not in node:
        node[key_part_1] = {}
    elif type(node[key_part_1]) is not dict:
        type_name = node[key_part_1]
        node[key_part_1] = {}
        node[key_part_1]["type"] = type_name
    is_valid_value,final_value = check_value(tag_key, element.attrib['v'])
    if is_valid_value:
        node[key_part_1][key_part_2] = final_value

# validate and convert value based on key. it return a tuple of the following
# boolean : indicating whether the validation was successful
# string : original or converted value, Empty string if validation fails 
def check_value(key, value): 
    if key == 'addr:country':
        m = canada.search(value)
        if m:
            return True,value
        problematic_elements["country"].append(value)
        return False,""
    if key == 'addr:province':
        m = ontario.search(value)
        if m:
            return True,value
        elif value in ontario_alternative:
            return True,"ON"
        problematic_elements["province"].append(value)
        return False,""
    if key == 'addr:city':        
        m = city.search(value)
        if m:
            return True,value
        elif value in toronto_alternative:
            return True,"Toronto"
        elif value in northyork_alternative:
            return True,"North York"
        elif value in eastyork_alternative:
            return True,"East York"
        problematic_elements["city"].append(value)
        return False,""
    if key == 'addr:postcode':        
        m = postcode.search(value)
        if m:
            return True,value
        ma = postcode_alternative.search(value)
        if ma:
            return True,value[:3]+" "+value[3:]
        problematic_elements["postcode"].append(value)
        return False,""
    if key == 'addr:street':        
        m = street.search(value)
        if m:
            saint_name = value[4:].split(' ')
            if value[0:4] == 'St. ' and saint_name[0] in SAINTS:
                return True, "Saint " + value[4:]
            problematic_elements["street"].append(value)
            return False,""
    
    return True,value

#match a regular expression with an item
def is_match(rg,item):
    m = rg.search(item)
    if m:
        return True
    return False

#main function
def process_map(file_in, pretty = False):
    # You do not need to change this file
    file_out = "{0}.json".format(file_in)
    data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data

data = process_map('toronto.osm', True)