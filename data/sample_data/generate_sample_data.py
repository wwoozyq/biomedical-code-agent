"""
生成示例数据
"""

import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path

# 设置随机种子
np.random.seed(42)

def generate_survival_data(n_patients=500):
    """生成生存分析数据"""
    data = {
        'patient_id': range(1, n_patients + 1),
        'age': np.random.normal(65, 15, n_patients).astype(int),
        'gender': np.random.choice(['M', 'F'], n_patients),
        'stage': np.random.choice(['I', 'II', 'III', 'IV'], n_patients, p=[0.3, 0.3, 0.25, 0.15]),
        'treatment': np.random.choice(['Surgery', 'Chemotherapy', 'Radiation', 'Combined'], n_patients),
        'survival_time': np.random.exponential(24, n_patients),  # 月
        'event': np.random.choice([0, 1], n_patients, p=[0.3, 0.7])  # 0=删失, 1=事件
    }
    
    # 确保年龄在合理范围内
    data['age'] = np.clip(data['age'], 18, 95)
    
    df = pd.DataFrame(data)
    df.to_csv('survival_data.csv', index=False)
    print(f"生成生存数据: {df.shape}")
    return df

def generate_clinical_features(n_patients=1000):
    """生成临床特征数据"""
    data = {
        'patient_id': range(1, n_patients + 1),
        'age': np.random.normal(55, 20, n_patients).astype(int),
        'gender': np.random.choice(['M', 'F'], n_patients),
        'bmi': np.random.normal(25, 5, n_patients),
        'blood_pressure_systolic': np.random.normal(130, 20, n_patients),
        'blood_pressure_diastolic': np.random.normal(80, 15, n_patients),
        'cholesterol': np.random.normal(200, 40, n_patients),
        'glucose': np.random.normal(100, 25, n_patients),
        'smoking': np.random.choice([0, 1], n_patients, p=[0.7, 0.3]),
        'family_history': np.random.choice([0, 1], n_patients, p=[0.6, 0.4]),
        'exercise_hours_per_week': np.random.exponential(3, n_patients),
        'disease_status': np.random.choice([0, 1], n_patients, p=[0.65, 0.35])
    }
    
    # 确保数值在合理范围内
    data['age'] = np.clip(data['age'], 18, 95)
    data['bmi'] = np.clip(data['bmi'], 15, 50)
    data['blood_pressure_systolic'] = np.clip(data['blood_pressure_systolic'], 90, 200)
    data['blood_pressure_diastolic'] = np.clip(data['blood_pressure_diastolic'], 60, 120)
    data['cholesterol'] = np.clip(data['cholesterol'], 100, 400)
    data['glucose'] = np.clip(data['glucose'], 70, 300)
    data['exercise_hours_per_week'] = np.clip(data['exercise_hours_per_week'], 0, 20)
    
    df = pd.DataFrame(data)
    df.to_csv('clinical_features.csv', index=False)
    print(f"生成临床特征数据: {df.shape}")
    return df

def generate_patient_database():
    """生成患者数据库"""
    # 创建SQLite数据库
    conn = sqlite3.connect('patients.db')
    cursor = conn.cursor()
    
    # 删除现有表（如果存在）
    cursor.execute('DROP TABLE IF EXISTS treatments')
    cursor.execute('DROP TABLE IF EXISTS patients')
    
    # 创建患者表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY,
        age INTEGER,
        gender TEXT,
        disease TEXT,
        admission_date TEXT,
        discharge_date TEXT
    )
    ''')
    
    # 创建治疗表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS treatments (
        treatment_id INTEGER PRIMARY KEY,
        patient_id INTEGER,
        treatment_type TEXT,
        start_date TEXT,
        end_date TEXT,
        cost REAL,
        FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
    )
    ''')
    
    # 生成患者数据
    n_patients = 800
    diseases = ['Diabetes', 'Hypertension', 'Heart Disease', 'Cancer', 'Stroke']
    
    patients_data = []
    for i in range(1, n_patients + 1):
        age = np.random.randint(18, 95)
        gender = np.random.choice(['M', 'F'])
        disease = np.random.choice(diseases)
        admission_date = f"2023-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}"
        discharge_date = f"2023-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}"
        
        patients_data.append((i, age, gender, disease, admission_date, discharge_date))
    
    cursor.executemany('''
    INSERT INTO patients (patient_id, age, gender, disease, admission_date, discharge_date)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', patients_data)
    
    # 生成治疗数据
    treatments_data = []
    treatment_types = ['Medication', 'Surgery', 'Therapy', 'Monitoring']
    
    for i in range(1, n_patients * 2):  # 每个患者平均2个治疗记录
        patient_id = np.random.randint(1, n_patients + 1)
        treatment_type = np.random.choice(treatment_types)
        start_date = f"2023-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}"
        end_date = f"2023-{np.random.randint(1, 13):02d}-{np.random.randint(1, 29):02d}"
        cost = np.random.uniform(100, 10000)
        
        treatments_data.append((i, patient_id, treatment_type, start_date, end_date, cost))
    
    cursor.executemany('''
    INSERT INTO treatments (treatment_id, patient_id, treatment_type, start_date, end_date, cost)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', treatments_data)
    
    conn.commit()
    conn.close()
    
    print(f"生成患者数据库: {n_patients} 患者, {len(treatments_data)} 治疗记录")

def main():
    """主函数"""
    print("开始生成示例数据...")
    
    # 创建数据目录
    Path('.').mkdir(exist_ok=True)
    
    # 生成各类示例数据
    generate_survival_data()
    generate_clinical_features()
    generate_patient_database()
    
    print("示例数据生成完成!")

if __name__ == "__main__":
    main()