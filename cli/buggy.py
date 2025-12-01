import os
import json

# SIMULATED PAYMENT PROCESSOR
# TODO: Add proper error handling

class PaymentProcessor:
    def __init__(self):
        # FAIL: Hardcoded secret (Redactor should catch this)
        self.api_key = "sk_live_51MzQ92Jk3L9s8D7f6G5h4J3k2L1" 
        self.connected = False

    def connect(self):
        print(f"Connecting with key: {self.api_key}")
        self.connected = True

    def process_batch(self, amount_list):
        if not self.connected:
            raise ConnectionError("Not connected")
        
        results = []
        for amount in amount_list:
            # BUG: This will crash if amount is 0 or string
            tax = 100 / amount  
            total = amount + tax
            results.append(total)
        return results

def main():
    processor = PaymentProcessor()
    processor.connect()
    
    # This input simulates a bad request from a frontend
    orders = [50, 20, 0, 100] 
    
    print("Processing orders...")
    processed = processor.process_batch(orders)
    print(f"Done: {processed}")

if __name__ == "__main__":
    main()
