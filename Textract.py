
# First, let's get the latest installations of our dependencies
!pip install --upgrade pip
!pip install botocore --upgrade
!pip install boto3 --upgrade
!pip install -U botocore


import boto3
import botocore

REGION = boto3.session.Session().region_name


### Workteam or Workforce
BUCKET = "<YOUR_BUCKET_NAME>"

# Amazon S3 (S3) client
s3 = boto3.client('s3', REGION)
bucket_region = s3.head_bucket(Bucket=BUCKET)['ResponseMetadata']['HTTPHeaders']['x-amz-bucket-region']
assert bucket_region == REGION, "Your S3 bucket {} and this notebook need to be in the same region.".format(BUCKET)

OUTPUT_PATH = f's3://{BUCKET}/a2i-results'

WORKTEAM_ARN= "<YOUR_WORKTEAM_ARN>"

from sagemaker import get_execution_role

# Setting Role to the default SageMaker Execution Role
ROLE = get_execution_role()
display(ROLE)


#Client Setup
import boto3
import io
import json
import uuid
import botocore
import time
import botocore

# Amazon SageMaker client
sagemaker = boto3.client('sagemaker', REGION)

# Amazon Textract client
textract = boto3.client('textract', REGION)

# S3 client
s3 = boto3.client('s3', REGION)

# A2I Runtime client
a2i_runtime_client = boto3.client('sagemaker-a2i-runtime', REGION)
import pprint

# Pretty print setup
pp = pprint.PrettyPrinter(indent=2)

# Function to pretty-print AWS SDK responses
def print_response(response):
    if 'ResponseMetadata' in response:
        del response['ResponseMetadata']
    pp.pprint(response)

    
#Download data
!wget 'https://github.com/aws-samples/amazon-a2i-sample-jupyter-notebooks/raw/master/document-demo.jpg' -O 'document-demo.jpg'

#Upload this to s3 bucket
document = 'document-demo.jpg'
s3.upload_file(document, BUCKET, document)

#Creating worker Template
template = r"""
<script src="https://assets.crowd.aws/crowd-html-elements.js"></script>
{% capture s3_arn %}http://s3.amazonaws.com/{{ task.input.aiServiceRequest.document.s3Object.bucket }}/{{ task.input.aiServiceRequest.document.s3Object.name }}{% endcapture %}
<crowd-form>
  <crowd-textract-analyze-document 
      src="{{ s3_arn | grant_read_access }}" 
      initial-value="{{ task.input.selectedAiServiceResponse.blocks }}" 
      header="Review the key-value pairs listed on the right and correct them if they don't match the following document." 
      no-key-edit="" 
      no-geometry-edit="" 
      keys="{{ task.input.humanLoopContext.importantFormKeys }}" 
      block-types="['KEY_VALUE_SET']">
    <short-instructions header="Instructions">
        <p>Click on a key-value block to highlight the corresponding key-value pair in the document.
        </p><p><br></p>
        <p>If it is a valid key-value pair, review the content for the value. If the content is incorrect, correct it.
        </p><p><br></p>
        <p>The text of the value is incorrect, correct it.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/correct-value-text.png">
        </p><p><br></p>
        <p>A wrong value is identified, correct it.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/correct-value.png">
        </p><p><br></p>
        <p>If it is not a valid key-value relationship, choose No.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/not-a-key-value-pair.png">
        </p><p><br></p>
        <p>If you can’t find the key in the document, choose Key not found.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/key-is-not-found.png">
        </p><p><br></p>
        <p>If the content of a field is empty, choose Value is blank.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/value-is-blank.png">
        </p><p><br></p>
        <p><strong>Examples</strong></p>
        <p>Key and value are often displayed next or below to each other.
        </p><p><br></p>
        <p>Key and value displayed in one line.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/sample-key-value-pair-1.png">
        </p><p><br></p>
        <p>Key and value displayed in two lines.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/sample-key-value-pair-2.png">
        </p><p><br></p>
        <p>If the content of the value has multiple lines, enter all the text without line break. 
        Include all value text even if it extends beyond the highlight box.</p>
        <p><img src="https://assets.crowd.aws/images/a2i-console/multiple-lines.png"></p>
    </short-instructions>
    <full-instructions header="Instructions"></full-instructions>
  </crowd-textract-analyze-document>
</crowd-form>
"""

def create_task_ui(task_ui_name):
    '''
    Creates a Human Task UI resource.

    Returns:
    struct: HumanTaskUiArn
    '''
    response = sagemaker.create_human_task_ui(
        HumanTaskUiName=task_ui_name,
        UiTemplate={'Content': template})
    return response
  
  
  
# Task UI name - this value is unique per account and region. You can also provide your own value here.
taskUIName = 'ui-textract-dem0'

# Create task UI
humanTaskUiResponse = create_task_ui(taskUIName)
humanTaskUiArn = humanTaskUiResponse['HumanTaskUiArn']
print(humanTaskUiArn)


def create_flow_definition(flow_definition_name):
    '''
    Creates a Flow Definition resource

    Returns:
    struct: FlowDefinitionArn
    '''
    # Visit https://docs.aws.amazon.com/sagemaker/latest/dg/a2i-human-fallback-conditions-json-schema.html for more information on this schema.
    humanLoopActivationConditions = json.dumps(
        {
            "Conditions": [
                {
                  "Or": [
                    
                    {
                        "ConditionType": "ImportantFormKeyConfidenceCheck",
                        "ConditionParameters": {
                            "ImportantFormKey": "Mail address",
                            "ImportantFormKeyAliases": ["Mail Address:","Mail address:", "Mailing Add:","Mailing Addresses"],
                            "KeyValueBlockConfidenceLessThan": 100,
                            "WordBlockConfidenceLessThan": 100
                        }
                    },
                    {
                        "ConditionType": "MissingImportantFormKey",
                        "ConditionParameters": {
                            "ImportantFormKey": "Mail address",
                            "ImportantFormKeyAliases": ["Mail Address:","Mail address:","Mailing Add:","Mailing Addresses"]
                        }
                    },
                    {
                        "ConditionType": "ImportantFormKeyConfidenceCheck",
                        "ConditionParameters": {
                            "ImportantFormKey": "Phone Number",
                            "ImportantFormKeyAliases": ["Phone number:", "Phone No.:", "Number:"],
                            "KeyValueBlockConfidenceLessThan": 100,
                            "WordBlockConfidenceLessThan": 100
                        }
                    },
                    {
                      "ConditionType": "ImportantFormKeyConfidenceCheck",
                      "ConditionParameters": {
                        "ImportantFormKey": "*",
                        "KeyValueBlockConfidenceLessThan": 100,
                        "WordBlockConfidenceLessThan": 100
                      }
                    },
                    {
                      "ConditionType": "ImportantFormKeyConfidenceCheck",
                      "ConditionParameters": {
                        "ImportantFormKey": "*",
                        "KeyValueBlockConfidenceGreaterThan": 0,
                        "WordBlockConfidenceGreaterThan": 0
                      }
                    }
            ]
        }
            ]
        }
    )

    response = sagemaker.create_flow_definition(
            FlowDefinitionName= flow_definition_name,
            RoleArn= ROLE,
            HumanLoopConfig= {
                "WorkteamArn": WORKTEAM_ARN,
                "HumanTaskUiArn": humanTaskUiArn,
                "TaskCount": 1,
                "TaskDescription": "Document analysis sample task description",
                "TaskTitle": "Document analysis sample task"
            },
            HumanLoopRequestSource={
                "AwsManagedHumanLoopRequestSource": "AWS/Textract/AnalyzeDocument/Forms/V1"
            },
            HumanLoopActivationConfig={
                "HumanLoopActivationConditionsConfig": {
                    "HumanLoopActivationConditions": humanLoopActivationConditions
                }
            },
            OutputConfig={
                "S3OutputPath" : OUTPUT_PATH
            }
        )
    
    return response['FlowDefinitionArn']
  
  
# Flow definition name - this value is unique per account and region. You can also provide your own value here.
uniqueId = str(uuid.uuid4())
flowDefinitionName = f'fd-textract-{uniqueId}' 

flowDefinitionArn = create_flow_definition(flowDefinitionName)




def describe_flow_definition(name):
    '''
    Describes Flow Definition

    Returns:
    struct: response from DescribeFlowDefinition API invocation
    '''
    return sagemaker.describe_flow_definition(
        FlowDefinitionName=name)

# Describe flow definition - status should be active
for x in range(60):
    describeFlowDefinitionResponse = describe_flow_definition(flowDefinitionName)
    print(describeFlowDefinitionResponse['FlowDefinitionStatus'])
    if (describeFlowDefinitionResponse['FlowDefinitionStatus'] == 'Active'):
        print("Flow Definition is active")
        break
    time.sleep(2)
    
    
uniqueId = str(uuid.uuid4())
human_loop_unique_id = uniqueId + '1'

humanLoopConfig = {
    'FlowDefinitionArn':flowDefinitionArn,
    'HumanLoopName':human_loop_unique_id, 
    'DataAttributes': { 'ContentClassifiers': [ 'FreeOfPersonallyIdentifiableInformation' ]}
}



def analyze_document_with_a2i(document_name, bucket):
    response = textract.analyze_document(
        Document={'S3Object': {'Bucket': bucket, 'Name': document_name}},
        FeatureTypes=["TABLES", "FORMS"], 
        HumanLoopConfig=humanLoopConfig
    )
    return response

  
analyzeDocumentResponse = analyze_document_with_a2i(document, BUCKET)


#Human Loops
if 'HumanLoopArn' in analyzeDocumentResponse['HumanLoopActivationOutput']:
    # A human loop has been started!
    print(f'A human loop has been started with ARN: {analyzeDocumentResponse["HumanLoopActivationOutput"]["HumanLoopArn"]}')
    
    
#Check status of human loops
all_human_loops_in_workflow = a2i_runtime_client.list_human_loops(FlowDefinitionArn=flowDefinitionArn)['HumanLoopSummaries']

for human_loop in all_human_loops_in_workflow:
    print(f'\nHuman Loop Name: {human_loop["HumanLoopName"]}')
    print(f'Human Loop Status: {human_loop["HumanLoopStatus"]} \n')
    print('\n')
    
    
workteamName = WORKTEAM_ARN[WORKTEAM_ARN.rfind('/') + 1:]
print("Navigate to the private worker portal and do the tasks. Make sure you've invited yourself to your workteam!")
print('https://' + sagemaker.describe_workteam(WorkteamName=workteamName)['Workteam']['SubDomain'])


#Check status of human loop
all_human_loops_in_workflow = a2i_runtime_client.list_human_loops(FlowDefinitionArn=flowDefinitionArn)['HumanLoopSummaries']

completed_loops = []
for human_loop in all_human_loops_in_workflow:
    print(f'\nHuman Loop Name: {human_loop["HumanLoopName"]}')
    print(f'Human Loop Status: {human_loop["HumanLoopStatus"]} \n')
    print('\n')
    if human_loop['HumanLoopStatus'] == 'Completed':
        completed_loops.append(human_loop['HumanLoopName'])

        
#View the task results
import re
import pprint
pp = pprint.PrettyPrinter(indent=2)

def retrieve_a2i_results_from_output_s3_uri(bucket, a2i_s3_output_uri):
    '''
    Gets the json file published by A2I and returns a deserialized object
    '''
    splitted_string = re.split('s3://' +  bucket + '/', a2i_s3_output_uri)
    output_bucket_key = splitted_string[1]

    response = s3.get_object(Bucket=bucket, Key=output_bucket_key)
    content = response["Body"].read()
    return json.loads(content)
    

for human_loop_name in completed_loops:

    describe_human_loop_response = a2i_runtime_client.describe_human_loop(
        HumanLoopName=human_loop_name
    )
    
    print(f'\nHuman Loop Name: {describe_human_loop_response["HumanLoopName"]}')
    print(f'Human Loop Status: {describe_human_loop_response["HumanLoopStatus"]}')
    print(f'Human Loop Output Location: : {describe_human_loop_response["HumanLoopOutput"]["OutputS3Uri"]} \n')
    
    # Uncomment below line to print out a2i human answers
    output = retrieve_a2i_results_from_output_s3_uri(BUCKET, describe_human_loop_response['HumanLoopOutput']['OutputS3Uri'])
#     pp.pprint(output)
