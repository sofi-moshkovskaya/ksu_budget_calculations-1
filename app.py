import csv
import json
import sys
from typing import Optional
import pandas as pd

INPUT_FILE_PATH = 'data/data.json'
INPUT_STUDENTS_QUANTITY_PATH = 'data/student_quantity.csv'
OUTPUT_FILE_PATH = 'data/result.json'


class Coefficient:
    def __init__(self, data: dict):
        self.A: float = data['A']
        self.RK: float = data['RK']
        self.M: float = data['M']
        self.RP: float = data['RP']
        self.N: float = data['N']
        self.MV: float = data['MV']
        self.PV: float = data['PV']

    def calculate_a(self):
        self.A = self.RK * self.M * self.RP * self.N * self.MV * self.PV
        return self.A


class Index:
    def __init__(self, data: dict):
        self.DENNA_IR: float = data['DENNA_IR']
        self.ZAOCHNA_IR: float = data['ZAOCHNA_IR']
        self.BACHELOR_IF: float = data['BACHELOR_IF']
        self.MASTER_IF: float = data['MASTER_IF']


class Budget:
    STUDENTS_AMOUNT = None
    BASE = None
    TOTAL = None
    STABLE = None
    INDEX_BASED = None
    SOCIAL_PAYMENTS = None

    def init(self, data: dict):
        self.STUDENTS_AMOUNT = data["STUDENTS_AMOUNT"]
        self.BASE = data["BASE"]
        self.TOTAL = data["TOTAL"]
        self.STABLE = data["STABLE"]
        self.INDEX_BASED = data["INDEX_BASED"]
        self.SOCIAL_PAYMENTS = data["SOCIAL_PAYMENTS"]
        return self


def correct_total(current_total, next_total, min_ratio, max_ratio):
    next_current_ratio = next_total / current_total

    if next_current_ratio < min_ratio:
        reserve = current_total * (min_ratio - next_current_ratio) / next_current_ratio
    elif next_current_ratio > max_ratio:
        reserve = current_total * (max_ratio - next_current_ratio) / next_current_ratio
    else:
        reserve = 0

    return next_total + reserve


def main(argv):
    with open(INPUT_FILE_PATH, mode='r') as file:
        input_data = json.load(file)

    with open(INPUT_STUDENTS_QUANTITY_PATH, mode='r') as file:
        students_quantity = pd.read_csv(file)
        students_quantity['Faculty'].fillna(method='ffill', inplace=True)

    # PROCESS DATA
    coefficient = Coefficient(input_data['COEFFICIENT'])
    index = Index(input_data['INDEX'])
    staff = pd.DataFrame(input_data['STAFF'].items(), columns=['Category', 'Value'])
    staff['Percent'] = staff['Value'] / staff['Value'].sum()

    base_next_current_ratio = input_data['BASE_NEXT_CURRENT_RATIO']
    min_ratio = input_data['MIN_RATIO']
    max_ratio = input_data['MAX_RATIO']

    current_budget = Budget().init(input_data['CURRENT'])

    next_budget = Budget()
    next_budget.INDEX_BASED = input_data['TMP_L'] * coefficient.calculate_a()
    next_budget.STABLE = input_data['STABILITY_COEFFICIENT'] * (current_budget.TOTAL - current_budget.SOCIAL_PAYMENTS)
    next_budget.SOCIAL_PAYMENTS = current_budget.SOCIAL_PAYMENTS

    next_budget.BASE = next_budget.STABLE + next_budget.INDEX_BASED  # !
    next_budget.TOTAL = correct_total(current_budget.BASE, next_budget.BASE, min_ratio, max_ratio)

    weights = pd.Series([
        index.DENNA_IR * index.BACHELOR_IF,
        index.DENNA_IR * index.MASTER_IF,
        index.ZAOCHNA_IR * index.BACHELOR_IF,
        index.ZAOCHNA_IR * index.MASTER_IF
    ], index=['DENNA_BACHELOR', 'DENNA_MASTER', 'ZAOCHNA_BACHELOR', 'ZAOCHNA_MASTER'])
    weighted_students = weights * students_quantity.iloc[:, 2:6]
    students_quantity['sum'] = weighted_students.sum(axis=1) * students_quantity['INDEX_IS']
    faculty_students_quantity = students_quantity[['Faculty', 'sum']].copy().groupby(['Faculty']).sum().reset_index()

    university_sum = faculty_students_quantity['sum'].sum()  # TODO rename column
    contingent_unit_value = next_budget.STABLE / university_sum

    faculty_budget = faculty_students_quantity.copy()
    faculty_budget['sum'] = faculty_budget['sum'] * contingent_unit_value

    staff_types = ['NPP', 'NDP', 'AUP']

    faculty_staff = faculty_budget[["Faculty", "sum"]].copy()

    faculty_staff = pd.concat([faculty_staff,pd.DataFrame(columns=staff_types)])
    faculty_staff[staff_types] = list(staff.T.iloc[2])
    for staff_type in staff_types:
        faculty_staff[staff_type] = faculty_staff[staff_type].mul(faculty_staff['sum'])

    # staff.loc[staff['Category'] == 'NPP']['Value']

    with open(OUTPUT_FILE_PATH, mode='w') as file:
        result = {
            # TODO fix dict representation
            "coefficients": coefficient.__dict__,
            "next_budget": next_budget.__dict__,
            "faculty_students_quantity": faculty_students_quantity.to_dict(),
            "faculty_budget": faculty_budget.to_dict(),
            "university_sum": university_sum,
            "contingent_unit_value": contingent_unit_value,
            'faculty_staff':{
                x: faculty_staff[["Faculty", x]].to_dict() for x in staff_types
            }
        }
        json.dump(result, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1:])
