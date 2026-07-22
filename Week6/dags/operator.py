from airflow.sdk import DAG

from datetime import timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

def python_transform(): 
    print("hello! Transform from python")

def python_transform2():
    pass
    

with DAG(
    description= "This is my first DAG",
    dag_id='test_dag_v2',
    schedule='0 9-15 * * 1-5'
) as dag:
    extract = BashOperator(task_id = 'extract',bash_command='echo "Hello I am extracting data"')

    transform1 = PythonOperator(task_id = 'transform1',python_callable=python_transform, retries=3,retry_delay=timedelta(seconds=5))
    transform2 = PythonOperator(task_id = 'transform2',python_callable=python_transform2, retries=3,retry_delay=timedelta(seconds=5))

    load = SQLExecuteQueryOperator(task_id = 'load',sql=["select 'hello'"],conn_id='ride_sharing_warehouse')

    extract >> [transform1,transform2] >> load
