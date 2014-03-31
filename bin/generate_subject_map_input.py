#/usr/bin/env python
"""

generate_subject_map_input.py -  Tool to generate patient-to-research subject mapping files based on inputs from REDCap projects 

"""
# Version 0.1 2013-11-18
__authors__ = "Mohan Das Katragadda"
__copyright__ = "Copyright 2014, University of Florida"
__license__ = "BSD 3-Clause"
__version__ = "0.1"
__email__ = "mohan88@ufl.edu"
__status__ = "Development"
from lxml import etree
import xml.etree.ElementTree as ET
import logging
from lxml import etree
import httplib
from urllib import urlencode
import os
import sys

# This addresses the issues with relative paths
file_dir = os.path.dirname(os.path.realpath(__file__))
goal_dir = os.path.join(file_dir, "../")
proj_root = os.path.abspath(goal_dir)+'/'
sys.path.insert(0, proj_root+'bin/utils/')
from sftp_transactions import sftp_transactions
from redcap_transactions import redcap_transactions
from GSMLogger import GSMLogger

def main():
    
    # Configure logging
    global gsmlogger
    gsmlogger = GSMLogger()
    gsmlogger.configure_logging()
    
    setup_json = proj_root+'config/setup.json'
    global setup
    setup = read_config(setup_json)
    site_catalog_file = proj_root+setup['site_catalog_gsmi']
    # Initialize Redcap Interface

    properties = redcap_transactions().init_redcap_interface(setup,setup['redcap_uri'], gsmlogger.logger)
    transform_xsl = setup['xml_formatting_tranform_xsl']
    response = redcap_transactions().get_data_from_redcap(properties,setup['token'], gsmlogger.logger,'RedCap')
    
    #XSL Transformation 1: This transformation removes junk data, rename elements and extracts site_id and adds new tag site_id
    xml_tree = etree.fromstring(response)
    xslt = etree.parse(proj_root+transform_xsl)
    transform = etree.XSLT(xslt)
    xml_transformed = transform(xml_tree)
    xml_str = etree.tostring(xml_transformed, method='xml', pretty_print=True)
    
    #XSL Transformation 2: This transformation groups the data based on site_id
    transform2_xsl = setup['groupby_siteid_transform_xsl']
    xslt = etree.parse(proj_root+transform2_xsl)
    transform = etree.XSLT(xslt)
    xml_transformed2 = transform(xml_transformed)
    
    #Prettifying the output generated by XSL Transformation
    xml_str2 = etree.tostring(xml_transformed2, method='xml', pretty_print=True)
    tree = etree.fromstring(xml_str2, etree.XMLParser(remove_blank_text=True))
    smi_filenames = []
    for k in tree:
        write_element_tree_to_file(ET.ElementTree(k),proj_root+'smi'+k.attrib['id']+'.xml')
        smi_filenames.append(k.attrib['id'])
    parse_site_details_and_send(site_catalog_file, smi_filenames)


def write_element_tree_to_file(element_tree, file_name):
    '''function to write ElementTree to a file
        takes file_name as input
        Radha

    '''
    gsmlogger.logger.debug('Writing ElementTree to %s', file_name)
    element_tree.write(file_name, encoding="us-ascii", xml_declaration=True,
            method="xml")

def parse_site_details_and_send(site_catalog_file, smi_filenames):
    '''Function to parse the site details from site catalog'''
    catalog_dict = {}
    for smi_file_no in smi_filenames:
        if not os.path.exists(proj_root+'smi'+smi_file_no+'.xml'):
            raise GSMLogger().LogException("Error: smi file "+smi_file+" file not found")
    if not os.path.exists(site_catalog_file):
        raise GSMLogger().LogException("Error: site_catalog xml file not found at \
            file not found at "+ site_catalog_file)
    else:
        catalog = open(site_catalog_file, 'r')
    site_data = etree.parse(site_catalog_file)
    site_num = len(site_data.findall(".//site"))
    gsmlogger.logger.info(str(site_num) + " total subject site entries read into tree.")
    sftp_instance = sftp_transactions()
    for site in site_data.iter('site'):
        site_code = site.findtext('site_code')
        if site_code in smi_filenames:
            site_URI = site.findtext('site_URI')
            site_uname = site.findtext('site_uname')
            site_password = site.findtext('site_password')
            site_contact_email = site.findtext('site_contact_email')
            '''Pick up the correct smi file with the code and place in the destination
            as smi.xml at the specified remote path
            
            '''
            file_name = 'smi'+site_code+'.xml'
            site_remotepath = site.findtext('site_remotepath')
            site_localpath = proj_root+file_name
            print 'Sending '+site_localpath+' to '+site_URI+':'+site_remotepath
            gsmlogger.logger.info('Sending %s to %s:%s', site_localpath, site_URI, site_remotepath)
            print 'Any error will be reported to '+site_contact_email
            gsmlogger.logger.info('Any error will be reported to %s',site_contact_email)
            sftp_instance.send_file_to_uri(site_URI, site_uname, site_password, site_remotepath, site_localpath, site_contact_email)
    catalog.close()
    gsmlogger.logger.info("site catalog XML file closed.")
    pass

        
def read_config(setup_json):
    """function to read the config data from setup.json
        Philip

    """
    import json

    try:
        json_data = open(setup_json)
    except IOError:
        #raise logger.error
        print "file " + setup_json + " could not be opened"
        raise

    setup = json.load(json_data)
    json_data.close()

    # test for required parameters
    required_parameters = ['source_data_schema_file', 'site_catalog_gsmi',
                    'system_log_file', 'redcap_uri', 'token']
    for parameter in required_parameters:
        if not parameter in setup:
            raise GSMLogger().LogException("read_config: required parameter, '"
            + parameter  + "', is not set in " + setup_json)

    # test for required files but only for the parameters that are set
    files = ['source_data_schema_file', 'site_catalog_gsmi', 'system_log_file']
    for item in files:
        if item in setup:
            if not os.path.exists(proj_root + setup[item]):
                raise GSMLogger().LogException("read_config: " + item + " file, '"
                        + setup[item] + "', specified in "
                        + setup_json + " does not exist")
    return setup
    

if __name__ == "__main__":
    main()