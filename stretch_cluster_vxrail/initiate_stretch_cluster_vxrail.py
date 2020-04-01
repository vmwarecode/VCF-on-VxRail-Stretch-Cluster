from argparse import ArgumentParser, RawTextHelpFormatter
from getpass import getpass
import requests
import time
import json


def sso_inputs():
    sso_username = input("Please enter SSO username : ")
    sso_password = getpass("Please provide SSO password : ")
    sso_confirm_password = getpass("Please confirm SSO password : ")
    if not sso_username or not sso_password or not sso_confirm_password:
        print('Please provide sso usename and password. Input field cannot be empty')
        exit(1)
    if sso_password != sso_confirm_password:
        print('SSO password mismatch. Please enter correct password')
        exit(1)
    return sso_username, sso_password


def get_cluster_id(input_domain_name, input_cluster_name, sso_username, sso_password):
    domains_json = get_request('http://localhost/v1/domains', sso_username, sso_password)

    clusters_in_domain = [domain['clusters'] for domain in domains_json['elements'] if
                          domain['name'] == input_domain_name]
    if not clusters_in_domain:
        print('Incorrect domain name Provided. Please provide correct domain name')
        exit(1)
    clusters_in_domain_ids = [cluster['id'] for cluster in clusters_in_domain[0]]

    clusters_json = get_request('http://localhost/v1/clusters', sso_username, sso_password)
    cluster_ids = [cluster['id'] for cluster in clusters_json['elements'] if cluster['name'] == input_cluster_name and
                   cluster['id'] in clusters_in_domain_ids]
    if not cluster_ids:
        print('Incorrect cluster name Provided. Please provide correct cluster name')
        exit(1)
    return cluster_ids[0]


def host_inputs(input_hosts_fqdn, workflow_option):
    hosts_fqdn = [x.strip() for x in input_hosts_fqdn.split(',')]
    hosts_list = []
    for host_fqdn in hosts_fqdn:
        host_ip = input('Please enter ip address for host %s : ' % host_fqdn)
        host_password = getpass('Please provide root user password for host %s : ' % host_fqdn)
        host_confirm_password = getpass('Please confirm root user password for host %s : ' % host_fqdn)
        if not host_ip or not host_password or not host_confirm_password:
            print('Please provide host details. Input field cannot be empty')
            exit(1)
        if host_password != host_confirm_password:
            print('For host %s, provided password and confirm password is not matching' % host_fqdn)
            exit(1)
        if workflow_option == 'stretch-vsan':
            hosts_list.append([host_ip, host_fqdn, host_password])
        elif workflow_option == 'expand-stretch-cluster':
            host_fault_domain = input('Please provide fault domain for host %s : ' % host_fqdn)
            if not host_fault_domain:
                print('Please provide host fault domain for host ' + host_fqdn + '. Input field cannot be empty')
                exit(1)
            hosts_list.append([host_ip, host_fqdn, host_password, host_fault_domain])
    return hosts_list


def vsan_inputs():
    vsan_spec = []
    vsan_gateway_ip_az1 = input('For preferred site: Please enter vSAN Gateway IP (ex: 172.18.93.1) : ')
    vsan_cidr_az1 = input('For preferred site: Please enter vSAN CIDR (ex: 172.18.93.0/24) : ')
    if not vsan_gateway_ip_az1 or not vsan_cidr_az1:
        print('Please provide vSAN gateway ip and vSAN CIDR for preferred site. Input field cannot be empty')
        exit(1)
    vsan_spec.append([vsan_gateway_ip_az1, vsan_cidr_az1])
    vsan_gateway_ip_az2 = input('For non-preferred site: Please enter vSAN Gateway IP (ex: 172.18.93.1) : ')
    vsan_cidr_az2 = input('For non-preferred site: Please enter vSAN CIDR (ex: 172.18.93.0/24) : ')
    if not vsan_gateway_ip_az2 or not vsan_cidr_az2:
        print('Please provide vSAN gateway ip and vSAN CIDR for non-preferred site. Input field cannot be '
              'empty')
        exit(1)
    vsan_spec.append([vsan_gateway_ip_az2, vsan_cidr_az2])
    return vsan_spec


def get_inputs(sc_hosts, workflow):
    sso_username, sso_password = sso_inputs()
    input_hosts_fqdn = sc_hosts
    hosts_list = host_inputs(input_hosts_fqdn, workflow)
    vsan_spec = vsan_inputs()
    return sso_username, sso_password, hosts_list, vsan_spec


def main():
    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.description = '''\nScript to simplify the configuration of vSAN Stretched Cluster with a VMware Cloud 
Foundation on VxRail Environment:\n\n'''
    parser.add_argument('--workflow', choices=['prepare-stretch', 'stretch-vsan', 'expand-stretch-cluster'],
                        required=True,
                        help='''Provide prepare-stretch, stretch-vsan or expand-stretch-cluster option
\nprepare-stretch: Perform vsan prepare stretch operation workflow,
should be called with following options 
--sc-domain 
--sc-cluster
Later with this option, script will prompt for following inputs
SSO username and SSO password 
\nstretch-vsan: Creates json payload for stretch vsan and executes 
workflow, should be called with following options 
-—sc-domain 
--sc-cluster 
--sc-hosts 
--witness-host-fqdn 
--witness-vsan-ip 
--witness-vsan-cidr 
Later with this option, script will prompt for following inputs
SSO username and SSO password 
ip-address and password for hosts provided with --sc-hosts option   
vSAN gateway ip and vSAN CIDR for preferred site and non-preferred site 
non-preferred site overlay vlan id
(Check help for supported params to be used for your environment and 
also refer Admin Guide for instructions)
\nexpand-stretch-cluster: Creates json payload for expand workflow, 
this operation is used for expansion of existing stretched cluster.
This operation must be run with 
--sc-domain 
--sc-cluster 
--sc-hosts 
--witness-host-fqdn 
--witness-vsan-ip 
--witness-vsan-cidr 
Later with this option, script will prompt for following inputs
SSO username and SSO password 
ip-address, password and fault domain for hosts provided with --sc-hosts option 
vSAN gateway ip and vSAN CIDR for preferred site and non-preferred site 
(Check help for supported params to be used for your environment and 
also refer Admin Guide for instructions)\n\n''')
    parser.add_argument('--sc-domain', help='Use this domain name for vsan stretch\n\n')
    parser.add_argument('--sc-cluster', help='Use this cluster name for vsan stretch workflow\n\n')
    parser.add_argument('--sc-hosts', help='Use these hosts for vsan stretch workflow (values: should be qualified '
                                           '\ndomain names) Sample: esx1.vsphere.local,esx-2.vsphere.local\n\n')
    parser.add_argument('--witness-host-fqdn', help='Witness Host fully qualified domain name or ip address\n\n')
    parser.add_argument('--witness-vsan-ip', help='Witness Host vsan ip address\n\n')
    parser.add_argument('--witness-vsan-cidr', help='Witness Host vsan cidr')

    args = parser.parse_args()

    if args.workflow == 'prepare-stretch' and args.sc_domain and args.sc_cluster:
        sso_username, sso_password = sso_inputs()
        print()
        cluster_id = get_cluster_id(args.sc_domain, args.sc_cluster, sso_username, sso_password)
        prepare_stretch(cluster_id, sso_username, sso_password)
    elif args.workflow == 'stretch-vsan' and args.sc_domain and args.sc_cluster and args.sc_hosts and args.witness_host_fqdn \
            and args.witness_vsan_ip and args.witness_vsan_cidr:
        sso_username, sso_password, hosts_list, vsan_spec = get_inputs(args.sc_hosts, args.workflow)
        overlay_vlan_id = input('Please enter non-preferred site overlay vlan id : ')
        if not overlay_vlan_id:
            print('Please provide non-preferred site overlay vlan id. Input field cannot be empty')
        print()
        cluster_id = get_cluster_id(args.sc_domain, args.sc_cluster, sso_username, sso_password)
        stretch_vsan_cluster(sso_username, sso_password, cluster_id, hosts_list, vsan_spec, args.witness_host_fqdn,
                             args.witness_vsan_ip, args.witness_vsan_cidr, overlay_vlan_id)
    elif args.workflow == 'expand-stretch-cluster' and args.sc_domain and args.sc_cluster and args.sc_hosts and args.witness_host_fqdn \
            and args.witness_vsan_ip and args.witness_vsan_cidr:
        sso_username, sso_password, hosts_list, vsan_spec = get_inputs(args.sc_hosts, args.workflow)
        print()
        cluster_id = get_cluster_id(args.sc_domain, args.sc_cluster, sso_username, sso_password)
        expand_stretch_cluster(sso_username, sso_password, cluster_id, hosts_list, vsan_spec, args.witness_host_fqdn,
                               args.witness_vsan_ip, args.witness_vsan_cidr)
    else:
        print('Please provide required arguments for workflow execution. Use -h option for more details')


def prepare_stretch(cluster_id, username, password):
    prepare_stretch_api = 'http://localhost/v1/clusters/' + cluster_id
    prepare_stretch_spec = {"prepareForStretch": True}
    response = patch_request(payload=prepare_stretch_spec, url=prepare_stretch_api, username=username,
                             password=password)
    print(response, end='\n\n')
    print('Workflow triggered, please track the task status in SDDC Manager UI')


def stretch_vsan_cluster(username, password, cluster_id, hosts_list, vsan_spec, witness_host_fqdn,
                         witness_vsan_ip, witness_vsan_cidr, overlay_vlan_id):
    stretch_validation_spec = {
        "hostSpecs": [],
        "witnessSpec": {
            "vsanIp": witness_vsan_ip,
            "fqdn": witness_host_fqdn,
            "vsanCidr": witness_vsan_cidr
        },
        "vsanNetworkSpecs": [],
        "secondaryAzOverlayVlanId": overlay_vlan_id
    }
    for h in hosts_list:
        esxi_id_dict = {'ipAddress': h[0], 'hostName': h[1], "username": "root", 'password': h[2]}
        stretch_validation_spec['hostSpecs'].append(esxi_id_dict)
    for v in vsan_spec:
        vsan_dict = {"vsanGatewayIP": v[0], "vsanCidr": v[1]}
        stretch_validation_spec['vsanNetworkSpecs'].append(vsan_dict)

    payload = {"clusterStretchSpec": stretch_validation_spec}
    execute_workflow(payload, username, password, cluster_id, 'vSAN stretch cluster')


def execute_workflow(payload, username, password, cluster_id, workflow_name):
    url = 'http://localhost/v1/clusters/'
    validation_url = url + cluster_id + '/validations'
    print('validation_url : ' + validation_url, end='\n\n')
    response = post_request(payload, validation_url, username, password)
    print('Validation started for ' + workflow_name + ' workflow. Validation response id : ' + response['id'], end='\n\n')

    stretch_validation_poll_url = url + 'validations/' + response['id']
    print('stretch_validation_poll_url : ' + stretch_validation_poll_url, end='\n\n')
    get_poll_request(stretch_validation_poll_url, username, password)
    print('Validation completed successfully for ' + workflow_name + ' workflow', end='\n\n')

    print('Triggering ' + workflow_name + ' workflow...', end='\n\n')
    execution_url = url + cluster_id
    print('execution_url : ' + execution_url, end='\n\n')
    response = patch_request(payload, execution_url, username, password)
    print(response, end='\n\n')
    print('Workflow triggered, please track the task status in SDDC Manager UI')


def expand_stretch_cluster(username, password, cluster_id, hosts_list, vsan_spec, witness_host_fqdn,
                           witness_vsan_ip, witness_vsan_cidr):
    stretch_expansion_spec = {
        "hostSpecs": [],
        "witnessSpec": {
            "vsanIp": witness_vsan_ip,
            "fqdn": witness_host_fqdn,
            "vsanCidr": witness_vsan_cidr
        },
        "vsanNetworkSpecs": []
    }
    for h in hosts_list:
        esxi_id_dict = {'ipAddress': h[0], 'hostName': h[1], "username": "root", 'password': h[2], 'azName': h[3]}
        stretch_expansion_spec['hostSpecs'].append(esxi_id_dict)
    for v in vsan_spec:
        vsan_dict = {"vsanGatewayIP": v[0], "vsanCidr": v[1]}
        stretch_expansion_spec['vsanNetworkSpecs'].append(vsan_dict)

    payload = {"clusterExpansionSpec": stretch_expansion_spec}
    execute_workflow(payload, username, password, cluster_id, 'expand stretch cluster')


def get_token(username, password):
    payload = {"username": username, "password": password}
    header = {'Content-Type': 'application/json'}
    token_url = 'http://localhost/v1/tokens'
    response = requests.post(token_url, headers=header, json=payload, verify=False)
    if response.status_code in [200, 202]:
        data = json.loads(response.text)
    else:
        print("Error reaching the server.")
        print(response.text)
        exit(1)
    token = data['accessToken']
    header['Authorization'] = 'Bearer ' + token
    return header


def get_request(url, username, password):
    header = get_token(username, password)
    response = requests.get(url, headers=header, verify=False)
    if response.status_code == 200:
        data = json.loads(response.text)
    else:
        print("Error reaching the server.")
        exit(1)
    print(data, end='\n\n')
    return data


def post_request(payload, url, username, password):
    header = get_token(username, password)
    response = requests.post(url, headers=header, json=payload, verify=False)
    if response.status_code in [200, 202]:
        data = json.loads(response.text)
        return data
    else:
        print("Error reaching the server.")
        print(response.text)
        exit(1)


def patch_request(payload, url, username, password):
    header = get_token(username, password)
    response = requests.patch(url, headers=header, json=payload, verify=False)
    if response.status_code in [200, 202]:
        data = json.loads(response.text)
        return data
    else:
        print("Error reaching the server.")
        print(response.text)
        exit(1)


def get_poll_request(url, username, password):
    status = get_request(url, username, password)['executionStatus']
    print(status, end='\n\n')
    while status in ['In Progress', 'IN_PROGRESS', 'Pending']:
        print('IN_PROGRESS', end='\n\n')
        time.sleep(10)
        response = get_request(url, username, password)
        status = response['executionStatus']

    if status == 'COMPLETED' and response['resultStatus'] == 'SUCCEEDED':
        return
    else:
        print('Validation failed')
        exit(1)


if __name__ == "__main__":
    main()
