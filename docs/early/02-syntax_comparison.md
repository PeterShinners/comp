# Comp Syntax Comparison

*How Comp syntax compares to equivalent code in other languages*

## Data Processing Pipeline

**Task:** Read CSV, filter high-value sales, calculate tax, write output

### Comp
```comp
"/data/sales.csv" 
-> io:read 
-> csv:parse 
=> {row -> row.amount > 1000 ? row | skip} 
=> {row -> {customer=row.name total=row.amount*1.1 tax=row.amount*0.15}} 
-> csv:stringify
-> io:write("/output/processed.csv")
```

### Python
```python
import pandas as pd

df = pd.read_csv("/data/sales.csv")
filtered = df[df['amount'] > 1000]
processed = filtered.assign(
    customer=filtered['name'],
    total=filtered['amount'] * 1.1,
    tax=filtered['amount'] * 0.15
)
processed.to_csv("/output/processed.csv", index=False)
```

### JavaScript
```javascript
const fs = require('fs');
const csv = require('csv-parser');
const createCsvWriter = require('csv-writer').createObjectCsvWriter;

const results = [];
fs.createReadStream('/data/sales.csv')
  .pipe(csv())
  .on('data', (row) => {
    if (row.amount > 1000) {
      results.push({
        customer: row.name,
        total: row.amount * 1.1,
        tax: row.amount * 0.15
      });
    }
  })
  .on('end', () => {
    const csvWriter = createCsvWriter({
      path: '/output/processed.csv',
      header: [
        {id: 'customer', title: 'customer'},
        {id: 'total', title: 'total'},
        {id: 'tax', title: 'tax'}
      ]
    });
    csvWriter.writeRecords(results);
  });
```

### SQL
```sql
-- Requires staging tables and multiple steps
CREATE TEMP TABLE filtered_sales AS
SELECT name as customer, amount * 1.1 as total, amount * 0.15 as tax
FROM sales 
WHERE amount > 1000;

-- Export would require additional tooling
```

## Error Handling

**Task:** Process data with graceful error handling

### Comp
```comp
"/data/input.json" 
-> io:read 
-> json:parse 
-> {data -> data.users => {user -> user.email@validate:email}} 
-> {emails -> emails@send:batch} 
-> {count -> "Sent ${count} emails"}
-> io:print
!> {error -> 
    "Processing failed: ${error.message}" -> log:error
    -> {error.type="email_error"} 
    -> error:report
}
```

### Python
```python
import json
import logging

try:
    with open("/data/input.json", 'r') as f:
        data = json.load(f)
    
    emails = []
    for user in data['users']:
        if validate_email(user['email']):
            emails.append(user['email'])
    
    send_batch_emails(emails)
    print(f"Sent {len(emails)} emails")
    
except Exception as error:
    logging.error(f"Processing failed: {error}")
    report_error({"type": "email_error", "message": str(error)})
```

### JavaScript
```javascript
const fs = require('fs').promises;

async function processEmails() {
  try {
    const content = await fs.readFile("/data/input.json", 'utf8');
    const data = JSON.parse(content);
    
    const validEmails = data.users
      .map(user => user.email)
      .filter(email => validateEmail(email));
    
    await sendBatchEmails(validEmails);
    console.log(`Sent ${validEmails.length} emails`);
    
  } catch (error) {
    console.error(`Processing failed: ${error.message}`);
    await reportError({type: "email_error", message: error.message});
  }
}
```

## Struct Manipulation

**Task:** Update nested data structures

### Comp
```comp
{
  user = {name="John" profile={age=30 city="NYC"}}
  updated = {
    ...user 
    profile = {...user.profile age=31 verified=true}
    last_updated = :time:now
  }
} -> database:save
```

### JavaScript
```javascript
const user = {
  name: "John", 
  profile: {age: 30, city: "NYC"}
};

const updated = {
  ...user,
  profile: {
    ...user.profile,
    age: 31,
    verified: true
  },
  last_updated: new Date()
};

database.save(updated);
```

## Conditional Processing

**Task:** Branch processing based on data characteristics

### Comp
```comp
data 
-> {item -> item.type == "premium"} 
? {item -> item -> premium:process -> {...result discount=0.2}}
| {item -> item -> standard:process}
-> billing:calculate
```

### Python
```python
def process_item(item):
    if item.type == "premium":
        result = premium_process(item)
        return {**result, "discount": 0.2}
    else:
        return standard_process(item)

processed = process_item(data)
bill = billing_calculate(processed)
```

### JavaScript
```javascript
const processItem = (item) => {
  if (item.type === "premium") {
    const result = premiumProcess(item);
    return {...result, discount: 0.2};
  } else {
    return standardProcess(item);
  }
};

const processed = processItem(data);
const bill = billingCalculate(processed);
```

---

*These comparisons demonstrate Comp's pipeline-based approach for common data processing tasks.*