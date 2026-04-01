import requests
import json

BASE_URL = "http://127.0.0.1:5000/api"

def test_transaction():
    print("Step 1: Fetching employees...")
    res = requests.get(f"{BASE_URL}/employees/")
    employees = res.json()
    if not employees:
        print("No employees found!")
        return
    
    emp_id = employees[0]["id"]
    print(f"Using employee: {employees[0]['name']} (ID: {emp_id})")

    print("\nStep 2: Generating a bill...")
    bill_data = {
        "employee_id": emp_id,
        "bill_date": "2026-03-31",
        "notes": "Testing transactions"
    }
    res = requests.post(f"{BASE_URL}/bills/generate", json=bill_data)
    bill = res.json()
    bill_id = bill.get("bill_id")
    print(f"Generated Bill #{bill_id} - Amount: {bill['net_amount']} - Status: {bill.get('status', 'UNPAID')}")

    print("\nStep 3: Paying the bill (This is the atomic transaction)...")
    pay_data = {
        "payment_method": "Credit Card",
        "transaction_ref": f"TXN-{bill_id}"
    }
    res = requests.post(f"{BASE_URL}/bills/pay/{bill_id}", json=pay_data)
    print(f"Response: {res.status_code}")
    print(json.dumps(res.json(), indent=2))

    print("\nStep 4: Verifying bill status again...")
    res = requests.get(f"{BASE_URL}/bills/{bill_id}")
    updated_bill = res.json()
    print(f"Bill #{bill_id} status: {updated_bill.get('status')}")

    if updated_bill.get("status") == "PAID":
        print("\nSUCCESS: Transaction completed atomically.")
    else:
        print("\nFAILURE: Status not updated.")

if __name__ == "__main__":
    test_transaction()
