# Chat System Guide

## Setup

### 1. Create User
```bash
curl -X POST "http://localhost:8000/api/register" -H "Content-Type: application/json" -d '{"email": "user@test.com", "password": "password123", "firstName": "John", "lastName": "Doe", "phone": "555-0123", "role": "user", "companyName": "Test Company", "address": "123 Main St", "city": "Test City", "state": "TS", "zipCode": "12345", "dotNumber": "123456", "mcNumber": "MC123456", "ein": "12-3456789", "businessType": "Freight", "yearsInBusiness": 5, "numberOfTrucks": 10}'
```

### 2. Login User
```bash
USER_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/login" -H "Content-Type: application/json" -d '{"email": "user@test.com", "password": "password123"}')
USER_ID=$(echo $USER_RESPONSE | jq -r '.user.id')
COMPANY_ID=$(echo $USER_RESPONSE | jq -r '.user.companyId')
JWT_TOKEN=$(echo $USER_RESPONSE | jq -r '.token')
```

### 3. Create Driver
```bash
DRIVER_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/fleet/drivers" -H "Content-Type: application/json" -H "Authorization: Bearer $JWT_TOKEN" -d '{"firstName": "Jane", "lastName": "Smith", "email": "driver@test.com", "phone": "+1234567890", "licenseNumber": "DL123456789", "licenseClass": "CDL-A", "licenseExpiry": "2025-12-31T00:00:00", "dateOfBirth": "1985-06-15T00:00:00", "address": "456 Driver Lane", "city": "Test City", "state": "TS", "zipCode": "12345", "emergencyContact": "John Doe", "emergencyPhone": "+1234567891", "hireDate": "2023-01-15T00:00:00", "payRate": 25.0, "payType": "hourly", "status": "available"}')
DRIVER_ID=$(echo $DRIVER_RESPONSE | jq -r '.id')
```

## Chat

### 4. Create Conversation
```bash
CONVERSATION_RESPONSE=$(curl -s -X POST "http://localhost:8000/chat/conversations?participant_id=$USER_ID&participant_type=user&company_id=$COMPANY_ID" -H "Content-Type: application/json" -d "{\"other_participant_id\": \"$DRIVER_ID\", \"other_participant_type\": \"driver\"}")
CONVERSATION_ID=$(echo $CONVERSATION_RESPONSE | jq -r '.id')
```

### 5. User Sends First Message
```bash
curl -X POST "http://localhost:8000/chat/messages?participant_id=$USER_ID&participant_type=user&company_id=$COMPANY_ID" -H "Content-Type: application/json" -d "{\"conversation_id\": \"$CONVERSATION_ID\", \"content\": \"Hello Jane! We have a new shipment from Chicago to Dallas. Can you handle it?\", \"message_type\": \"text\"}"
```

### 6. Driver Replies
```bash
curl -X POST "http://localhost:8000/chat/messages?participant_id=$DRIVER_ID&participant_type=driver&company_id=$COMPANY_ID" -H "Content-Type: application/json" -d "{\"conversation_id\": \"$CONVERSATION_ID\", \"content\": \"Hi John! Yes, I can handle it. What time is the pickup?\", \"message_type\": \"text\"}"
```

### 7. User Sends Second Message
```bash
curl -X POST "http://localhost:8000/chat/messages?participant_id=$USER_ID&participant_type=user&company_id=$COMPANY_ID" -H "Content-Type: application/json" -d "{\"conversation_id\": \"$CONVERSATION_ID\", \"content\": \"Pickup is at 8 AM tomorrow. The load is 20,000 lbs. Are you ready?\", \"message_type\": \"text\"}"
```

### 8. Driver Sends Second Reply
```bash
curl -X POST "http://localhost:8000/chat/messages?participant_id=$DRIVER_ID&participant_type=driver&company_id=$COMPANY_ID" -H "Content-Type: application/json" -d "{\"conversation_id\": \"$CONVERSATION_ID\", \"content\": \"Perfect! I'll be there at 7:30 AM. My truck can handle 25,000 lbs. See you tomorrow!\", \"message_type\": \"text\"}"
```

### 9. View Messages
```bash
curl -X GET "http://localhost:8000/chat/conversations/$CONVERSATION_ID/messages?participant_id=$USER_ID&participant_type=user&company_id=$COMPANY_ID"
```

### 10. View All Conversations
```bash
curl -X GET "http://localhost:8000/chat/conversations?participant_id=$USER_ID&participant_type=user&company_id=$COMPANY_ID"
```