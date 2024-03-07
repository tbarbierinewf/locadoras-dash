import pandas as pd
import botocore
import boto3
import os, io
import json
from typing import Union

class S3Facilities(object):
    def __init__(self, bucket_name:str, region_name:str):
        print("Initializing AWS...")
        self.bucket_name = bucket_name

        region_name = os.environ.get('AWS_DEFAULT_REGION')
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

        if os.environ.get('AWS_ENV') == 'dev':
            self.client = boto3.client('s3',
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
            self.resource = boto3.resource('s3',
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
        else:
            self.session = boto3.Session()
            self.client = self.session.client('s3')
            self.resource = self.session.resource('s3')

        self.ec2 = boto3.client('ec2', region_name=region_name)
        self.bucket = self.resource.Bucket(bucket_name)

        print("Connected successfully!")

    def list_files(self, prefix:str='', endswith:str='', dont:str=None, get_objects:bool=False) -> list:
        '''
        List files from the actual bucket.
        prefix: filter the files according to the name beginnning.
        endswith: filter the files according to the name ending.
        dont: remove files that have the string you insert contained in the file name.
        '''
        objects = self.bucket.objects.filter(Prefix=prefix)

        keys = []
        for item in objects:
            if item.key.endswith(endswith):
                if dont == None:
                    keys.append(item.key)
                elif dont not in item.key:
                    keys.append(item.key)
        if get_objects == True:
            return keys, objects
        
        return keys
    
    def put_file(self, file:Union[str,list,dict,pd.DataFrame], key:str, sep:str=',', encoding_type:str="utf-8", index:bool=True):
        """
        Upload file to AWS's actual bucket.
        file: upload data to S3 according to the type of input.
            Case:
                str: consider the string as the directory of the file to upload.
                list: consider it is a json data and convert it to json.
                DataFrame: a csv file is built
        key: the Key that the file is about to receive inside AWS S3.
        sep: is a conditional input that is only used for DataFrames. It defines the csv file separator.
        encoding_type: type of encoding (eg: 'latin-1', 'utf-8', 'iso-891'...) in case of pd.DataFrame or JSON
        index: set if the DataFrame should have an index or don't.
        """
        if isinstance(file, str):
            with open(file, 'rb') as f:
                file_obj = f.read()
        elif isinstance(file, list) or isinstance(file, dict):
            json_data = json.dumps(file)
            encoded_data = json_data.encode(encoding_type)
            file_obj = io.BytesIO(encoded_data)
        elif isinstance(file, pd.DataFrame):
            df_str = file.to_csv(sep=sep, index=index)
            encoded_data = df_str.encode(encoding_type)
            file_obj = io.BytesIO(encoded_data)

        self.client.put_object(Body=file_obj, Bucket=self.bucket_name, Key=key)
        print(f"File '{file_obj}' uploaded successfully to S3!")

    def download_file(self, file_name:str, directory:str='', bucket_name:str=''):
        """
        Download file from AWS S3.
        file_name: is the file key.
        directory: the local directory you want the file to be downloaded in.
        bucket_name: in case you need to download a file from a different bucket. Default is the actual bucket.
        """
        print(f"Downloading '{file_name}...'")
        if bucket_name == '':
            bucket_name = self.bucket_name
        if directory == '':
            directory = f"/tmp/{file_name.split('/')[-1]}"
        self.client.download_file(bucket_name, file_name, directory)

    def get_object(self, file_name:str, directory='', **kwargs):
        """
        This method downloads the file but already returns it as a variable.
        file_name: file key.
        directory: only used if get_object is True. Defines the directory for the file to be downloaded.
        sep: if you already want to read a csv file and the separator is different of ',' you can set it here.
        """
        self.download_file(file_name, directory=directory)
        if file_name.endswith('.json'):
            with open(f"/tmp/{file_name.split('/')[-1]}", 'r') as f:
                return json.load(f)
        elif file_name.endswith('.csv'):
            return pd.read_csv(f"/tmp/{file_name.split('/')[-1]}", **kwargs)
        elif file_name.endswith('.txt'):
            with open(f"/tmp/{file_name.split('/')[-1]}", 'r') as f:
                return f.read()
        else:
            with open(f"/tmp/{file_name.split('/')[-1]}", 'r') as f:
                return f.read()
                
    def file_exists(self, file_name:str, bucket_name:str='', get_object:bool=False, directory:str='', sep:str=',') -> Union[list,pd.DataFrame,bool]:
        """
        Check if file existis on AWS S3.
        file_name: file key.
        bucket_name: the bucket from where you want to download the file. Default is the actual bucket.
        get_object: if True, downloads the file if it exists.
        directory: only used if get_object is True. Defines the directory for the file to be downloaded.
        sep: if you already want to read a csv file and the separator is different of ',' you can set it here.
        """
        if bucket_name == '':
            bucket_name = self.bucket_name
        try:
            self.resource.Object(bucket_name, file_name).load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                if get_object == True:
                    print(f"File {file_name} doesn't exists.")
                    return []
                return False
            
        if get_object == True:
            return self.get_object(file_name=file_name, directory=directory, sep=sep)
        return True
    
    def delete_object(self, file_name:str, bucket_name:str=''):
        """
        Delete object from AWS S3.
        file_name: file key.
        bucket_name: bucket where the file is located. Default is the actual bucket.
        """
        if bucket_name == '':
            bucket_name = self.bucket_name
        response = self.client.delete_object(
            Bucket=bucket_name,
            Key=file_name,
        )
        return response
    
    def copy_object(self, old_key:str, new_key:str, source_bucket:str='', destination_bucket:str=''):
        """
        Changes a file's location.
        old_key: actual file key.
        new_key: desired file key.
        source_bucket: actual file bucket.
        destination_bucket: desired file bucket.
        """
        if destination_bucket == '':
            destination_bucket = self.bucket_name
        if source_bucket == '':
            source_bucket = self.bucket_name

        response = self.client.copy_object(
            Bucket=destination_bucket,
            CopySource=f'{source_bucket}/{old_key}',
            Key=new_key,
        )

        return response
    
    def rename_object(self, old_key:str, new_key:str, source_bucket:str='', destination_bucket:str=''):
        """
        This method accually does a copy of the defined file and deletes the older one.
        old_key: actual file key.
        new_key: desired file key.
        source_bucket: actual file bucket.
        destination_bucket: desired file bucket.
        """
        if destination_bucket == '':
            destination_bucket = self.bucket_name
        if source_bucket == '':
            source_bucket = self.bucket_name

        self.copy_object(old_key, new_key)
        self.delete_object(old_key)

    def stop_ec2(self, id:Union[str, list]):
        """
        EC2 interruption.
        id: EC2 Instance ID.
        """
        if isinstance(id, str):
            self.ec2.stop_instances(InstanceIds=[id])
        elif isinstance(id, list):
            self.ec2.stop_instances(InstanceIds=id)