""" This python class serves as a utility wrapper around the API. That being said, this was created to quickly update and stand up AWX Towers based on a given
directory structure that flatly represents your organization -> job template architecture.

The structure is like the following:
.../manifest
        Organization
            Project 
                Inventory
                    Job Templates
The script will then walk through the manifest directory and creating orgs, projects, inventories, and templates as appropriate.
While seemingly extra, this allows you to programatically update job templates via file system while maintaining at least some sort of 'spacial' organization while managing your Tower at bulk scale.

This probably won't fit your use case, so feel free to create PRs that can extend off of this.

@author Andrew Subowo - Open to free use to general public

Works best with Python 3, if you're cool
"""
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import json
import os
import sys
import requests
import signal
import re
import fileinput

headers={'Content-type':'application/json'}
# Tower endpoint should end with /api/v2/
api = os.getenv("AWX_ENDPOINT")
user = os.getenv("AWX_UTILS_USER")
password = os.getenv("AWX_UTILS_PASSWORD")

def signal_handler(sig, frame):
    print("")
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def scan_manifest_dir(directory):
    for org in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, org)):
            print(str(org))
        for project in os.listdir(os.path.join(directory, org)):
            if os.path.isdir(os.path.join(directory, org, project)):
                print("\t" + str(project))
            for inv in os.listdir(os.path.join(directory, org, project)):
                if os.path.isdir(os.path.join(directory, org, project, inv)):
                    print("\t\t" + str(inv))
                for template in os.listdir(os.path.join(directory, org, project, inv)):
                    if template.lower().endswith('.json'):
                        print("\t\t\t" + str(template))

def get_job_templates():
    url = api + "job_templates/"
    json_raw = requests.get(url, auth=(user, password))
    return json_raw.json()

def get_job_template_id(templateName):
    data = get_job_templates()
    templateID = 0
    for results in data['results']:
        if templateName == results['name']:
            templateID = results['id']
    if templateID == 0:
        return -1
    else:
        return templateID

# Disgusting way to enforce a decent directory layout from 
# https://docs.ansible.com/ansible/latest/user_guide/sample_setup.html#alternative-directory-layout
def create_templates_from_manifest_dir(dir_from_arg = ""):
    if dir_from_arg == "":
        print("If executing with Python 2.x, please encapsulate your directory with \"\"")
        directory = input("Please provide the absolute path to the manifest directory: ")
    else:
        directory = dir_from_arg

    if "manifest" not in directory:
        print("The path given is not a manifest directory (e.g. /tmp/ansible/manifest)")
        return -1

    if not os.path.exists(directory):
        print(str(directory) + " is not a valid directory")
        return -1
    
    print("Attempting to build manifest from " + str(directory) + "...")

    scan_manifest_dir(directory)     
    input("Does this look correct? If so, press ENTER to continue. Otherwise press CTRL + C to halt.")

    for org in os.listdir(directory):
        if os.path.isdir(os.path.join(directory, org)):
            create_organization(org)
        for project in os.listdir(os.path.join(directory, org)):
            if os.path.isdir(os.path.join(directory, org, project)):               
                create_project(project, org)
            for inv in os.listdir(os.path.join(directory, org, project)):
                if os.path.isdir(os.path.join(directory, org, project, inv)):                 
                    create_inventory(inv, org)
                for template in os.listdir(os.path.join(directory, org, project, inv)):
                    if template.lower().endswith('.json'):
                        template_path = os.path.join(directory, org, project, inv, template)   
                        orgID = get_org_id(org)
                        invID = get_inventory_id(inv)        
                        projectID = get_project_id(project)
                        if orgID != -1 and invID != -1 and projectID != -1:       
                            with open(template_path, 'r') as file:
                                temp = file.read()
                                temp = temp.replace("ORG", str(orgID))
                                temp = temp.replace("INV", str(invID))
                                temp = temp.replace("PRO", str(projectID))
                            with open(template_path, 'w') as file:
                                file.write(temp)
                            create_job_template_from_file(template_path)
                        else:
                            print("Skipping " + template_path + ". Please ensure your manifest is set up correctly.")

def create_job_template_from_file(template):
    url = api + "job_templates/"
    contents = open(template, 'rb').read()

    attempt = requests.post(url, auth=(user, password), data=contents, headers=headers)
    if attempt.status_code == 201:
        print("Successfully built template")
        return 0
    elif attempt.status_code == 400:
        print("Job template already exists, attempting to update...")
        update_job_template_from_file(template)
    else:
        print("Could not build " + str(template))
        print(attempt.status_code)
        print(attempt.text)

# NOTE: ALL fields must be present in a json file to perform an update request
# template : str, required - A stringish path to somewhere on the filesystem representing a JSON file
def update_job_template_from_file(template):

    # Parse JSON in file to get job template name
    with open(template, 'rb') as f:
        data = json.load(f)
        contents = f.read()
    templateName = data['name']
    templateID = get_job_template_id(templateName)

    if (templateID == -1):
        print("Could not find a job template named " + templateName)
        return -1

    url = api + "job_templates/" + str(templateID)

    attempt = requests.post(url, auth=(user, password), data=contents, headers=headers)
    if attempt.status_code == 201 or attempt.status_code == 200:
        print(attempt.text)
        print("Template updated successfully.")
        return 0
    else:
        print("Could not update " + templateName)
        print(attempt.status_code)
        print(attempt.text)

def get_all_inventories():
    url = api + "inventories/"
    json_raw = requests.get(url, auth=(user, password))
    return json_raw.json()

def get_inventory_id(invName):
    data = get_all_inventories()
    invID = 0
    for results in data['results']:
        if invName == results['name']:
            invID = results['id']
    if invID == 0:
        return -1
    else:
        return invID

def create_inventory(invName, orgName):
    orgID = get_org_id(orgName)
    url = api + "inventories/"
    data = get_all_inventories()
    foundInvs = []
    for results in data['results']:
        foundInvs.append(results['name'])
    
    if invName in foundInvs:
        print(str(invName) + " already exists.")
    else:
        payload = { 'name': invName, 'organization': orgID }
        build = requests.post(url, auth=(user, password), json=payload, headers=headers)  
        if build.status_code == 201:
            print("Successfully created " + str(invName))
        else:
            print("Error creating " + str(invName))
            print(build.status_code)
            print(build.text)
            return -1

def get_all_org():
    url = api + "organizations/"
    json_raw = requests.get(url, auth=(user, password))
    return json_raw.json()

def get_org_id(orgName):
    data = get_all_org()
    orgID = 0
    for results in data['results']:
        if orgName == results['name']:
            orgID = results['id']
    if orgID == 0:
        return -1
    else:
        return orgID

def create_organization(orgName):
    url = api + "organizations/"
    data = get_all_org()
    foundOrgs = []
    for results in data['results']:
        foundOrgs.append(results['name'])

    if orgName in foundOrgs:
        print(orgName + " already exists. Skipping.")
    else:
        payload = { 'name': orgName }
        build = requests.post(url, auth=(user, password), json=payload, headers=headers)
        if (build.status_code == 201):
            print(orgName + " created successfully.")
            return 0

def get_all_projects():
    url = api + "projects/"
    json_raw = requests.get(url, auth=(user, password))
    return json_raw.json()

def get_project_id(projectName):
    data = get_all_projects()  
    projectID = 0
    for results in data['results']:
        if projectName == results['name']:
            projectID = results['id']
    if projectID == 0:
        return -1
    else:
        return projectID

def create_project(projectName, orgName):
    orgID = get_org_id(orgName)

    url = api + "projects/"
    data = get_all_projects()
    foundProjects = []
    for results in data['results']:
        foundProjects.append(results['name'])

    if projectName in foundProjects:
        print(projectName + " already exists. Skipping.")
    else:
        path = projectName
        payload = { 'name': projectName, 'local_path': path, 'organization': orgID }
        
        attempt = requests.post(url, auth=(user, password), json=payload, headers=headers)
        # 201 success
        # 400 already in use/exists
        if (attempt.status_code == 201 or attempt.status_code == 400):
            print(projectName + " created successfully.")
            return 0
        else:
            print(attempt.status_code)
            print(attempt.text)
        
""" A convoluted method to update a project via API
projectName : str, required
    The name of the project you want to update
orgName : str, required
    The name of the organization this project belongs to
description : str, optional
    A description for this project
path : str, optional
    The name of the directory that contains roles this project will be pointing at
scmType : str, optional
    The type of SCM this project will be using. Defaults to 'manual'
scmURL : str, optional
    Based on the SCM used, the URL to use to update projects using SCM.
scmRefspec : str, optional
"""
def update_project_path(projectName, orgName, description="", path="", scmType='', scmUrl="", scmBranch="", scmRefspec="", scmClean=False, scmDeleteOnUpdate=False, credential=' ', timeout=0,  scmUpdateOnLaunch=False, scmUpdateCacheTimeout=0, allowOverride=False, customVEnv=''):
    orgID = get_org_id(orgName)
    projectID = get_project_id(projectName)
    url = api + "projects/" + str(projectID)
    path = '/var/lib/awx/projects/' + projectName

    payload = { 'name': projectName, 'description': '', 'local_path': path, 'scm_type': scmType, 'scm_url': scmUrl, 'scm_branch': scmBranch, 'scm_refspec': scmRefspec, 'scm_clean': scmClean, 'scm_delete_on_update': scmDeleteOnUpdate, 'credential': credential, 'timeout': timeout, 'organization': orgID, 'scm_update_on_launch': scmUpdateOnLaunch, 'scm_update_cache_timeout': scmUpdateCacheTimeout, 'allow_override': allowOverride, 'custom_virtualenv': customVEnv}

    attempt = requests.put(url, auth=(user, password), json=payload, headers=headers)

    print(attempt.text)

create_templates_from_manifest_dir()