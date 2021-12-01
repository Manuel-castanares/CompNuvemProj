from typing import Protocol
import boto3
import time

#Pegando client
ec2_client = boto3.client("ec2", region_name='us-east-2')
ec2_client_NV = boto3.client("ec2", region_name='us-east-1')
client_LB = boto3.client("elb", region_name='us-east-1')
client_LB2 = boto3.client("elbv2", region_name='us-east-1')
client_AG = boto3.client("autoscaling", region_name='us-east-1')

#Pegando resource
ec2_resource = boto3.resource("ec2", region_name='us-east-2')
ec2_resource_NV = boto3.resource("ec2", region_name='us-east-1')

#Imagem de Linux 18.04 LTS 
Image = "ami-020db2c14939a8efb"
Image_NV = "ami-0279c3b3186e54acd"

#Pegando Security Group
SecGroupId = ec2_client.describe_security_groups()["SecurityGroups"][0]["GroupId"]
SecGroupName = ec2_client.describe_security_groups()["SecurityGroups"][0]["GroupName"]

#Pegando senha da base de dados
f = open("Sec.txt", 'r')
password = f.readline()
f.close()

#Script para rodar no UserData
userdata = f"""#!/bin/bash
apt update
apt install postgresql postgresql-contrib -y
echo "CREATE USER manuel PASSWORD '{password}'" > /home/ubuntu/user.sql
sudo -u postgres psql --file=/home/ubuntu/user.sql
echo "CREATE DATABASE tasks WITH OWNER manuel" > /home/ubuntu/tasks.sql
sudo -u postgres psql --file=/home/ubuntu/tasks.sql
echo "ALTER SYSTEM SET listen_addresses TO '*'" > /home/ubuntu/alter.sql
sudo -u postgres psql --file=/home/ubuntu/alter.sql
echo "host    all             all             0.0.0.0/0               password" >> /../etc/postgresql/10/main/pg_hba.conf
ufw allow 5432/tcp
systemctl restart postgresql
"""

def split_string(lb_arn, tg_arn):
    resource_name1 = lb_arn.split("/", 1)
    resource_name2 = tg_arn.split("/", 1)
    resource_name = f"{resource_name1[1]}/targetgroup/{resource_name2[1]}"
    print(f"nome do recurso: {resource_name}")
    return resource_name 


#Funcao que cria loadbalancer
def create_lbv2(client):
    response = client.create_load_balancer(
    Name='my-load-balancer',
    Subnets=[
        'subnet-2698ee29',
        'subnet-7239875c',
        'subnet-7bb2001c',
        'subnet-aa935294',
        'subnet-b2c281f8',
        'subnet-fa56eaa6',
    ],
    )
    return response

#Target Group
def create_TG(client):
    response = client.create_target_group(
        Name='my-TG',
        Protocol='HTTP',
        Port=8080,
        TargetType='instance',
        VpcId='vpc-c59a57bf',
        HealthCheckPath='/admin/',
        Matcher = {
                'HttpCode': '200,302',
        },
    )
    return response

#Listener do loadbalancer
def create_listener(client, LB, TG):
    response = client.create_listener(
        LoadBalancerArn = LB,
        Protocol='HTTP',
        Port=80,
        DefaultActions = [
            {
                'TargetGroupArn': TG,
                'Type': 'forward',
            }
        ]
    )
    return response


#Funcao que cria configuracao de AG
def launch_config(cliente, image_id, tipo, userdata):
    response = cliente.create_launch_configuration(
        LaunchConfigurationName='my-launch-config',
        ImageId=str(image_id),
        InstanceType=tipo,
        SecurityGroups=[
            'sg-0c1ce2b0620f64637',
        ],
        #UserData=userdata,
    )
    return response

#Cria AG
def launch_AG(cliente, imagem, userdata, tg_arn):
    LC = launch_config(cliente, imagem, "t2.micro", userdata)
    time.sleep(30)
    response = cliente.create_auto_scaling_group(
        AutoScalingGroupName="my-AG",
        LaunchConfigurationName="my-launch-config",
        MinSize=1,
        MaxSize=5,
        DesiredCapacity=1,
        AvailabilityZones=[
            'us-east-1a', 'us-east-1b', 'us-east-1c', 'us-east-1d', 'us-east-1e', 'us-east-1f'
        ],
        TargetGroupARNs=[
            tg_arn,
        ],
    )
    return response

def put_policy(client, resource_name):
    response = client.put_scaling_policy(
    AutoScalingGroupName='my-AG',
    PolicyName='target-tracking-scaling-policy',
    PolicyType='TargetTrackingScaling',
    TargetTrackingConfiguration={
        'PredefinedMetricSpecification': {
            'PredefinedMetricType': 'ALBRequestCountPerTarget',
            'ResourceLabel': resource_name,
        },
        'TargetValue': 2.0,
    },
    )
    print("Policy adicionada ao autoscaling group. \n")



#Funcao que cria Instancia
def cria_instancia(resource, Imagem, Tipo, Chave, SecurityGroup, userdata, nome):
    instancia_criada = resource.create_instances(
    ImageId=Imagem, 
    MinCount=1, 
    MaxCount=1, 
    InstanceType=Tipo, 
    KeyName=Chave,
    BlockDeviceMappings = [
        {
            "DeviceName": "/dev/xvda",
            "Ebs":{
                "DeleteOnTermination": True,
                "VolumeSize": 8 
            }
        }
    ],
    SecurityGroups = [SecurityGroup],
    UserData = userdata,
    TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': 'Name',
                    'Value': nome
                },
            ]
        },
    ],
    )
    return instancia_criada

#funcao que registra a instancia no loadbalancer
def reg_inst(cliente, id_instancia):
    response = cliente.register_instances_with_load_balancer(
    Instances=[
        {
            'InstanceId': id_instancia,
        },
    ],
    LoadBalancerName='my-load-balancer',
    )
    return response

all_insts = ec2_resource.instances.all()
all_insts_NV = ec2_resource_NV.instances.all()

for instance in all_insts:
    if(instance.state["Name"] != "running"):
        print("Procurando instâncias que estão rodando \n")
    else:
        for tag in instance.tags:
            if tag["Value"] == "Instancia":
                instance.terminate()
                print("Deletando instâncias... \n")

for instance in all_insts_NV:
    if(instance.state["Name"] != "running"):
        print("Procurando instâncias que estão rodando \n")
    else:
        for tag in instance.tags:
            if tag["Value"] == "Instancia_Django":
                instance.terminate()
                print("Deletando instâncias... \n")



try:
    cria_instancia(ec2_resource, Image, "t2.micro", "ManuelOhio", "launch-wizard-1", userdata, "Instancia")
    print("Criando instância postgresql \n")
    time.sleep(180)
except Exception as e:
    print(e)

all_insts = ec2_resource.instances.all()

for instance in all_insts:
    if(instance.state["Name"] != "running"):
        print("esperando subir banco de dados")
    else:
        for tag in instance.tags:
            if tag["Value"] == "Instancia":
                ip_postgres= instance.public_ip_address
                print("Pegando ip da instância postgresql")

all_images = ec2_resource_NV.images.all()

for image in all_images:
    if image.name == "Imagem_Django":
        print("Deletando Imagens antigas... \n")
        image.deregister()



userdata_django= f"""#!/bin/bash
apt update
git clone https://github.com/Manuel-castanares/tasks.git
sed -i 's/node1/{ip_postgres}/' /../tasks/portfolio/settings.py
sed -i '0,/cloud/s/cloud/manuel/' /../tasks/portfolio/settings.py
sed -i 's/cloud/{password}/' /../tasks/portfolio/settings.py
apt install python3-dev libpq-dev python3-pip -y
python3 -m pip install -r /../tasks/requirements.txt
python3 /../tasks/manage.py migrate
echo '@reboot cd /../tasks && ./run.sh' | crontab
export DJANGO_SUPERUSER_PASSWORD={password}
export DJANGO_SUPERUSER_USERNAME=cloud
export DJANGO_SUPERUSER_EMAIL=cloud@a.com
python3 /../tasks/manage.py createsuperuser --noinput
reboot
"""

try:
    print("Criando instância Django \n")
    time.sleep(160)
    cria_instancia(ec2_resource_NV, Image_NV, "t2.micro", "Manuel", "launch-wizard-1", userdata_django, "Instancia_Django")
    time.sleep(320)
    print("Instância Django criada. \n")
except Exception as e:
    print(e)

all_insts_NV = ec2_resource_NV.instances.all()

for instance in all_insts_NV:
    #print(instance.state)
    if(instance.state["Name"] != "running"):
        print("Procurando instâncias que estão rodando \n")
    else:
        for tag in instance.tags:
            if tag["Value"] == "Instancia_Django":
                id_instancia = instance.instance_id
                print("Pegando IP da instância Django \n") 


imagem_dj = ec2_client_NV.create_image(InstanceId=id_instancia, Name="Imagem_Django", NoReboot=True)
time.sleep(70)
#print(imagem_dj)
#print(imagem_dj["ImageId"])


lbs = client_LB.describe_load_balancers()

for lb in lbs["LoadBalancerDescriptions"]:
    if lb["LoadBalancerName"] == "my-load-balancer":
        client_LB.delete_load_balancer(LoadBalancerName="my-load-balancer")

try:
    print("Criando loadbalancer e targetgroup \n")
    #create_lb(client_LB)
    lbv2 = create_lbv2(client_LB2)
    TG = create_TG(client_LB2)
    time.sleep(80)
    #print("LB2:   ")
    #print(lbv2["LoadBalancers"][0]["LoadBalancerArn"])
    lb_arn = lbv2["LoadBalancers"][0]["LoadBalancerArn"]
    #print("TG:    ")
    #print(TG["TargetGroups"][0]["TargetGroupArn"])
    tg_arn = TG["TargetGroups"][0]["TargetGroupArn"]
    resource_tag = split_string(lb_arn, tg_arn)
    #reg_inst(client_LB, id_instancia)
except Exception as e:
    print(e)


try:
    print("Criando listener do loadbalancer \n")
    create_listener(client_LB2, lb_arn, tg_arn)
    time.sleep(120)
except Exception as e:
    print(e)

##############################################################################################

try:
    print("Criando autoscaling group \n")
    launch_AG(client_AG, imagem_dj["ImageId"], userdata_django, tg_arn)
    time.sleep(120)
except Exception as e:
    print(e)

#response = client_LB.describe_target_groups(LoadBalancerArn=)

try:
    print("Criando policy e colocando no autoscaling group \n")
    put_policy(client_AG, resource_tag)
    time.sleep(30)
except Exception as e:
    print(e)


all_insts_NV = ec2_resource_NV.instances.all()

for instance in all_insts_NV:
    if(instance.state["Name"] != "running"):
        print("Procurando instâncias que estão rodando \n")
    else:
        for tag in instance.tags:
            if tag["Value"] == "Instancia_Django":
                instance.terminate()
                print("Apagando instância Django \n")

LBDNS = client_LB2.describe_load_balancers()

#print(LBDNS)
dnsLB = LBDNS["LoadBalancers"][0]["DNSName"]
print("Salvando DNS do Loadbalancer em um arquivo de texto. \n")

f = open("DNS.txt", "w")
f.write(dnsLB)
f.close()


