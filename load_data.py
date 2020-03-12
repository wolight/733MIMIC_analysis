from pyspark.sql import SparkSession, functions as F, types, Row
cluster_seeds = ['127.0.0.1']
spark = SparkSession.builder.appName('Spark Cassandra example').config('spark.cassandra.connection.host', ','.join(cluster_seeds)).getOrCreate()
assert spark.version >= '2.4' # make sure we have Spark 2.4+
spark.sparkContext.setLogLevel('WARN')
sc = spark.sparkContext


def load_patients():
    df = spark.read.format("csv").option("header", "true").load("PATIENTS.csv.gz")
    df = df.select("SUBJECT_ID","DOB")
    df = df.withColumnRenamed("SUBJECT_ID", "subject_id")
    df = df.withColumnRenamed("DOB", "dob")

    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("DONE WITH PATIENTS.")

def load_admissions():
    adm_schema = types.StructType([
        types.StructField('row_id', types.IntegerType()),
        types.StructField('subject_id', types.IntegerType()),
        types.StructField('hadm_id', types.IntegerType()),
        types.StructField('admittime', types.TimestampType()),
        types.StructField('dischtime', types.TimestampType()),
        types.StructField('deathtime', types.TimestampType()),
        types.StructField('admission_type', types.StringType()),
        types.StructField('admission_location', types.StringType()),
        types.StructField('discharge_location', types.StringType()),
        types.StructField('insurance', types.StringType()),
        types.StructField('language', types.StringType()),
        types.StructField('religion', types.StringType()),
        types.StructField('marital_status', types.StringType()),
        types.StructField('ethnicity', types.StringType()),
        types.StructField('edregtimen', types.TimestampType()),
        types.StructField('edouttimen', types.TimestampType()),
        types.StructField('diagnosis', types.StringType()),
        types.StructField('hospital_expire_flag', types.IntegerType()),
        types.StructField('has_chartevents_flag', types.IntegerType()),
    ])
    df = spark.read.csv("ADMISSIONS.csv.gz", schema = adm_schema)
    df = df.select("subject_id","hadm_id","admittime","dischtime","admission_type","hospital_expire_flag")
    df = df[(df.hadm_id.isNotNull())&(df.subject_id.isNotNull())]
    df.show()
    df.write.format("org.apache.spark.sql.cassandra").options(table='admissions', keyspace='mimic').save()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("DONE WITH ADMISSIONS.")


def load_labitems(item_n):
    event_schema = types.StructType([
        types.StructField('row_id', types.IntegerType()),
        types.StructField('subject_id', types.IntegerType()),
        types.StructField('hadm_id', types.IntegerType()),
        types.StructField('itemid', types.IntegerType()),
        types.StructField('charttime', types.TimestampType()),
        types.StructField('value', types.StringType()),
        types.StructField('valuenum', types.FloatType()),
        types.StructField('valueuom', types.StringType()),
        types.StructField('flag', types.BooleanType()),
    ])

    df = spark.read.csv("LABEVENTS.csv.gz", schema = event_schema)
    df = df[df.itemid == item_n]
    df = df.select('row_id','hadm_id','subject_id','charttime', 'valuenum','valueuom')
    df = df.filter(df.hadm_id.isNotNull() & df.subject_id.isNotNull() & df.valuenum.isNotNull())
    print(df.schema)
    df.show()
    df.write.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n), keyspace='mimic').save()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("DONE WITH LABELITEMS.")

def load_outputitems(item_n1, item_n2):
    event_schema = types.StructType([
        types.StructField('row_id', types.IntegerType()),
        types.StructField('subject_id', types.IntegerType()),
        types.StructField('hadm_id', types.IntegerType()),
        types.StructField('icustay_id', types.IntegerType()),
        types.StructField('charttime', types.TimestampType()),
        types.StructField('itemid', types.IntegerType()),
        types.StructField('value', types.DoubleType()),
        types.StructField('valueuom', types.StringType()),
        types.StructField('storetime', types.TimestampType()),
        types.StructField('cgid', types.LongType()),
        types.StructField('stopped', types.StringType()),
        types.StructField('newbottle', types.IntegerType()),
        types.StructField('iserror', types.ShortType()),
    ])

    df = spark.read.csv("OUTPUTEVENTS.csv.gz", schema = event_schema)
    df = df[(df.itemid == item_n1) | (df.itemid == item_n2)]
    df = df.select('row_id','hadm_id','subject_id','charttime', 'value','valueuom')
    df = df.withColumnRenamed("value", "valuenum")
    df = df.filter(df.hadm_id.isNotNull() & df.subject_id.isNotNull() & df.valuenum.isNotNull())
    print(df.schema)
    df.show()
    df.write.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n2), keyspace='mimic').save()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("DONE WITH OUTPUTLITEMS.")


def check_valueuom(item_n, uom):
    df = spark.read.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n), keyspace='mimic').load()
    total_n = df.count()
    null_n = df.filter(df.valueuom.isNull()).count()
    majority_n = df[(df.valueuom == uom)].count()
    others = df[(df.valueuom.isNotNull()) & (df.valueuom != uom)].show()
    print("Number of rows: "+str(total_n))
    print("Number of rows whose valueuom is null: "+str(null_n))
    print("Number of rows whose valueuom is "+uom+" or Deg. F: "+str(majority_n))
    print("Number of rows whose valueuom is not null and not "+uom+": "+str(total_n - null_n - majority_n))


def save_first_record(item_n):
    df = spark.read.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n), keyspace='mimic').load()
    df = df[(df.itemid == 51) | (df.itemid == 220050)]
    df_min_ct = df.groupby(["hadm_id","subject_id"]).agg(F.min(df["charttime"]))
    df_min_ct = df_min_ct.withColumnRenamed("min(charttime)", "charttime")
    df_min_ct.show()
    df_result = df_min_ct.join(df, ["hadm_id","subject_id","charttime"]).select(["hadm_id","subject_id","charttime","valuenum","itemid"])
    df_result.show()
    df_result.write.format("org.apache.spark.sql.cassandra").options(table="item"+str(item_n), keyspace='mimic').save()


def show_diff(item_n, num1, num2):
    df = spark.read.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n), keyspace='mimic').load()
    #df = df[(df.valueuom == uom) | (df.valueuom.isNull())]
    #print(df.count())
    df1 = df[(df.itemid == num1)]
    df2 = df[(df.itemid == num2)]
    df1 = df1.groupby(["hadm_id","subject_id"]).agg(F.min(df1["charttime"])).withColumnRenamed("min(charttime)", "charttime").join(df1, ["hadm_id","subject_id","charttime"]).select(["hadm_id","subject_id","charttime","itemid","valuenum"])
    df2 = df2.groupby(["hadm_id","subject_id"]).agg(F.min(df2["charttime"])).withColumnRenamed("min(charttime)", "charttime").join(df2, ["hadm_id","subject_id","charttime"]).select(["hadm_id","subject_id","charttime","itemid","valuenum"])
    df_result = df1.join(df2, ["hadm_id"])
    df_result.show()
    df[(df.itemid == item_n)].groupby(["hadm_id","subject_id"]).agg(F.min(df["charttime"])).withColumnRenamed("min(charttime)", "charttime").join(df, ["hadm_id","subject_id","charttime"]).select(["hadm_id","subject_id","charttime","itemid","valuenum"]).show()

def load_chartitems(item_n1, item_n2, item_n3, item_n4):
    event_schema = types.StructType([
        types.StructField('row_id', types.IntegerType()),
        types.StructField('subject_id', types.IntegerType()),
        types.StructField('hadm_id', types.IntegerType()),
        types.StructField('icustay_id', types.IntegerType()),
        types.StructField('itemid', types.IntegerType()),
        types.StructField('charttime', types.TimestampType()),
        types.StructField('storetime', types.TimestampType()),
        types.StructField('cgid', types.IntegerType()),
        types.StructField('value', types.StringType()),
        types.StructField('valuenum', types.FloatType()),
        types.StructField('valueuom', types.StringType()),
        types.StructField('warning', types.IntegerType()),
        types.StructField('error', types.IntegerType()),
        types.StructField('resultstatus', types.StringType()),
        types.StructField('stopped', types.StringType()),
    ])
  
    df = spark.read.csv("CHARTEVENTS.csv.gz", schema = event_schema)
    df = df[(df.itemid == item_n1) | (df.itemid == item_n2) | (df.itemid == item_n3) | (df.itemid == item_n4)]
    print(df.head(2))
    df = df.select('row_id','hadm_id','subject_id','charttime', 'valuenum','valueuom', 'itemid')
    df = df.filter(df.hadm_id.isNotNull() & df.subject_id.isNotNull() & df.valuenum.isNotNull())
    #df.show()
    df.write.format("org.apache.spark.sql.cassandra").options(table='temp'+str(item_n2), keyspace='mimic').save()
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    print("DONE WITH CHARTITEMS.")

def concat_features():
    admissions = spark.read.format("org.apache.spark.sql.cassandra").options(table='admissions', keyspace='mimic').load()
    patients = spark.read.format("org.apache.spark.sql.cassandra").options(table='patients', keyspace='mimic').load()
    df_result = admissions.join(patients, ["subject_id"])
    #df_result = df_result.select("subject_id","hadm_id","dob","admittime","dischtizme","admission_type","hospital_expire_flag", (F.year("admittime")-F.year("dob")).alias("age"))
    df_result = df_result.select("subject_id","hadm_id","admission_type","hospital_expire_flag", (F.year("admittime")-F.year("dob")).alias("age"))
    df_result = df_result.filter(df_result.age > 15)
    
    df51006 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item51006', keyspace='mimic').load()
    df_result = df_result.join(df51006, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item51006")
    
    df51301 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item51301', keyspace='mimic').load()
    df_result = df_result.join(df51301, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item51301")

    df50882 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item50882', keyspace='mimic').load()
    df_result = df_result.join(df50882, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item50882")

    df50983 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item50983', keyspace='mimic').load()
    df_result = df_result.join(df50983, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item50983")

    df50971 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item50971', keyspace='mimic').load()
    df_result = df_result.join(df50971, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item50971")

    df50821 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item50821', keyspace='mimic').load()
    df_result = df_result.join(df50821, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item50821")

    df226559 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item226559', keyspace='mimic').load()
    df_result = df_result.join(df226559, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item226559")

    df223900 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item223900', keyspace='mimic').load()
    df_result = df_result.join(df223900, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item223900")

    df223901 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item223901', keyspace='mimic').load()
    df_result = df_result.join(df223901, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item223901")

    df220739 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item220739', keyspace='mimic').load()
    df_result = df_result.join(df220739, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item220739")

    df220045 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item220045', keyspace='mimic').load()
    df_result = df_result.join(df220045, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item220045")

    df223761 = spark.read.format("org.apache.spark.sql.cassandra").options(table='item223761', keyspace='mimic').load()
    df_result = df_result.join(df223761, ["subject_id","hadm_id"]).drop("charttime").withColumnRenamed("valuenum", "item223761")

    df_result.write.format("org.apache.spark.sql.cassandra").options(table='motality_features_1', keyspace='mimic').save()  
    #df_result.show()
    #print(admissions.count())
    #print(df_result.count())
    print("FINISHED")

if __name__== "__main__":
  #load_patients()
  #load_admissions()
  #load_labitems(item_n)
  #load_outputitems(item_n1, item_n2)
  item_n1 = 3420
  item_n2 = 223835
  item_n3 = 3422
  item_n4 = 190
  concat_features()
  #uom = "%"
  #load_chartitems(item_n1, item_n2, item_n3, item_n4)
  #check_valueuom(item_n2, uom)
  #show_diff(item_n2, item_n1, item_n3)
  #save_first_record(item_n2)
