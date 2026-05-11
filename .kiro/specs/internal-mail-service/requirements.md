# Requirements Document: Internal Mail Service

## Introduction

The Internal Mail Service is a cross-module communication system for the ERP that enables employees to exchange messages and share live ERP resources within the organization. Unlike traditional email systems, this service treats shared resources (purchase orders, production orders, inventory items, etc.) as interactive widgets that provide direct navigation to the actual ERP records. The system maintains clean architectural boundaries by operating as an independent application layer that imports from other modules but is never imported by them.

## Glossary

- **Mail_System**: The internal mail service application that manages message creation, delivery, and resource attachment
- **Message**: An immutable communication record containing subject, body, sender, and recipients
- **Draft**: A message in editable state before being sent (is_draft=True)
- **Sent_Message**: A message that has been delivered to recipients and is now immutable (is_draft=False)
- **Recipient_Record**: Per-recipient state tracking for a message (MessageRecipient model)
- **Resource_Widget**: An interactive UI component representing an attached ERP resource
- **Shareable_Resource**: An ERP entity from the whitelist that can be attached to messages
- **Resource_Label**: A snapshot of resource metadata captured at message send time
- **Notification**: A delivery awareness record informing recipients of new messages
- **Thread**: A conversation chain where messages reference a parent message
- **Soft_Delete**: Marking a message as deleted without removing it from the database
- **Inbox**: A user's collection of received messages
- **Sent_Folder**: A user's collection of messages they have sent
- **BCC_Recipient**: A blind carbon copy recipient hidden from other recipients
- **Access_Verification**: Permission check to ensure users can view attached resources

## Requirements

### Requirement 1: Message Creation and Draft Management

**User Story:** As an ERP user, I want to create draft messages with subject, body, and recipients, so that I can compose communications before sending them.

#### Acceptance Criteria

1. WHEN a user creates a new message, THE Mail_System SHALL create a Message record with status='DRAFT' and is_draft=True
2. WHEN a Draft is created, THE Mail_System SHALL set sent_at to NULL
3. WHEN a user edits a Draft, THE Mail_System SHALL allow modification of subject and body fields
4. WHEN a user attempts to edit a Sent_Message, THE Mail_System SHALL reject the modification and return an error
5. THE Mail_System SHALL require subject to be non-empty and maximum 255 characters
6. THE Mail_System SHALL require body to be non-empty and maximum 10,000 characters
7. WHEN a Draft is created, THE Mail_System SHALL store the sender reference with PROTECT deletion behavior

### Requirement 2: Message Sending and Immutability

**User Story:** As an ERP user, I want to send draft messages to recipients, so that they receive my communication and attached resources.

#### Acceptance Criteria

1. WHEN a user sends a Draft, THE Mail_System SHALL transition the message status from 'DRAFT' to 'SENT'
2. WHEN a Draft is sent, THE Mail_System SHALL set is_draft to False
3. WHEN a Draft is sent, THE Mail_System SHALL set sent_at to the current timestamp
4. WHEN a Draft is sent, THE Mail_System SHALL require at least one recipient
5. WHEN a message transitions to SENT status, THE Mail_System SHALL make the subject and body immutable
6. WHEN a user attempts to send a non-Draft message, THE Mail_System SHALL reject the operation and return an error
7. WHEN a Draft is sent, THE Mail_System SHALL create Recipient_Record entries for all specified recipients

### Requirement 3: Recipient Management and Types

**User Story:** As an ERP user, I want to specify recipients as TO, CC, or BCC, so that I can control message visibility and recipient awareness.

#### Acceptance Criteria

1. WHEN a user adds a recipient, THE Mail_System SHALL validate that the recipient user ID exists and is active
2. WHEN a user specifies a recipient type, THE Mail_System SHALL accept only 'TO', 'CC', or 'BCC' values
3. WHEN no recipient type is specified, THE Mail_System SHALL default to 'TO'
4. WHEN a message is sent, THE Mail_System SHALL create one Recipient_Record per recipient with the specified type
5. WHEN a message has multiple recipients, THE Mail_System SHALL enforce uniqueness of (message, recipient) combinations
6. THE Mail_System SHALL limit the maximum number of recipients per message to 50

### Requirement 4: Per-Recipient State Management

**User Story:** As a message recipient, I want my read/unread, archived, and deleted states to be independent of other recipients, so that I can manage my inbox without affecting others.

#### Acceptance Criteria

1. WHEN a Recipient_Record is created, THE Mail_System SHALL initialize is_read to False, is_archived to False, and is_deleted to False
2. WHEN a recipient marks a message as read, THE Mail_System SHALL set is_read to True and read_at to the current timestamp for that Recipient_Record only
3. WHEN a recipient marks a message as unread, THE Mail_System SHALL set is_read to False and read_at to NULL for that Recipient_Record only
4. WHEN a recipient archives a message, THE Mail_System SHALL set is_archived to True for that Recipient_Record only
5. WHEN a recipient deletes a message, THE Mail_System SHALL set is_deleted to True and deleted_at to the current timestamp for that Recipient_Record only
6. WHEN a recipient modifies their message state, THE Mail_System SHALL not affect any other recipient's state for the same message
7. WHEN a recipient assigns a folder label, THE Mail_System SHALL store it in that Recipient_Record only

### Requirement 5: Resource Attachment to Messages

**User Story:** As an ERP user, I want to attach live ERP resources to messages, so that recipients can navigate directly to those resources in the system.

#### Acceptance Criteria

1. WHEN a user attaches a resource to a Draft, THE Mail_System SHALL validate that the resource type is in the SHAREABLE_RESOURCES whitelist
2. WHEN a user attaches a resource, THE Mail_System SHALL validate that the resource object exists in the database
3. WHEN a user attaches a resource, THE Mail_System SHALL verify that the user has access permission to that resource
4. WHEN a resource is attached, THE Mail_System SHALL create a MessageResource record with content_type and object_id
5. WHEN a resource is attached, THE Mail_System SHALL capture the resource_label from the resource's current state
6. WHEN a resource is attached, THE Mail_System SHALL set resource_type_display to a human-readable name
7. WHEN a resource is attached, THE Mail_System SHALL record the attached_by user reference
8. WHEN a user attempts to attach a resource to a Sent_Message, THE Mail_System SHALL reject the operation
9. WHEN a user attempts to attach a non-whitelisted resource type, THE Mail_System SHALL reject the operation and return an error

### Requirement 6: Resource Access Verification

**User Story:** As a system administrator, I want resource access to be verified when attaching and viewing resources, so that users cannot access resources they don't have permission to see.

#### Acceptance Criteria

1. WHEN a user attaches a resource, THE Mail_System SHALL verify the user has view permission on that resource before creating the MessageResource record
2. WHEN a recipient views an attached resource, THE Mail_System SHALL re-verify that the recipient has view permission on that resource
3. WHEN a user lacks permission to view a resource, THE Mail_System SHALL display "Access denied" and prevent navigation
4. WHEN a resource object is deleted from the ERP, THE Mail_System SHALL display "Resource no longer available" when recipients attempt to view it
5. THE Mail_System SHALL apply role-based access control rules specific to each resource type
6. WHEN verifying access to a PurchaseOrder, THE Mail_System SHALL grant access if the user role is in ['purchasing_officer', 'manager', 'owner_director', 'system_admin'] or the user is the creator
7. WHEN verifying access to a ProductionOrder, THE Mail_System SHALL grant access if the user role is in ['production_operator', 'production_supervisor', 'manager', 'owner_director', 'system_admin'] or the resource warehouse is in the user's accessible warehouses
8. WHEN verifying access to a StockMovement, THE Mail_System SHALL grant access if the user role is in ['warehouse_staff', 'inventory_controller', 'manager', 'owner_director', 'system_admin'] or the resource warehouse is in the user's accessible warehouses

### Requirement 7: Resource Label Immutability

**User Story:** As an ERP user, I want resource labels to be snapshots captured at send time, so that message history accurately reflects the resource state when the message was sent.

#### Acceptance Criteria

1. WHEN a Draft with attached resources is sent, THE Mail_System SHALL capture the resource_label from each resource's current state
2. WHEN a message transitions to SENT status, THE Mail_System SHALL make all resource_label values immutable
3. WHEN a resource's state changes in the ERP after a message is sent, THE Mail_System SHALL not update the resource_label in the MessageResource record
4. WHEN a recipient views a Sent_Message, THE Mail_System SHALL display the immutable resource_label captured at send time

### Requirement 8: Shareable Resources Whitelist

**User Story:** As a system architect, I want a controlled whitelist of shareable resource types, so that only appropriate ERP entities can be attached to messages.

#### Acceptance Criteria

1. THE Mail_System SHALL maintain a whitelist of 32 shareable resource types across 7 ERP modules
2. THE Mail_System SHALL include the following Purchasing module resources in the whitelist: PurchaseRequisition, PurchaseOrder, GoodsReceipt, SupplierInvoice, Supplier, SupplierProduct
3. THE Mail_System SHALL include the following Production module resources in the whitelist: ProductionOrder, ProductionBatch, ReworkOrder
4. THE Mail_System SHALL include the following Inventory module resources in the whitelist: StockMovement, Stock, Batch, ProductPolicy, InventoryAlert
5. THE Mail_System SHALL include the following Sales module resources in the whitelist: SalesOrder, Delivery, Invoice, Payment, Customer
6. THE Mail_System SHALL include the following Costing module resources in the whitelist: CostingEntry, StandardCost, CostVarianceRecord, OverheadRate, ProductPricingRule
7. THE Mail_System SHALL include the following Finance module resources in the whitelist: AccountsReceivable, AccountsPayable, SupplierPayment
8. THE Mail_System SHALL include the following Accounting module resources in the whitelist: JournalEntry
9. THE Mail_System SHALL include the following Central module resources in the whitelist: Product, Warehouse
10. WHEN a user attempts to attach a resource type not in the whitelist, THE Mail_System SHALL reject the operation

### Requirement 9: Notification Creation and Delivery

**User Story:** As a message recipient, I want to be notified when I receive new messages or replies, so that I am aware of communications requiring my attention.

#### Acceptance Criteria

1. WHEN a message is sent, THE Mail_System SHALL create one MailNotification record per recipient
2. WHEN a message is sent as a new conversation, THE Mail_System SHALL set notification_type to 'NEW_MESSAGE'
3. WHEN a message is sent as a reply to an existing message, THE Mail_System SHALL set notification_type to 'NEW_REPLY'
4. WHEN a user is mentioned in a message, THE Mail_System SHALL create a notification with notification_type 'MENTIONED'
5. WHEN a notification is created, THE Mail_System SHALL initialize is_dismissed to False
6. WHEN a notification is created, THE Mail_System SHALL set created_at to the current timestamp
7. WHEN a message is sent, THE Mail_System SHALL trigger real-time notification delivery via WebSocket

### Requirement 10: Notification Management

**User Story:** As an ERP user, I want to dismiss notifications and manage notification preferences, so that I can control my notification experience.

#### Acceptance Criteria

1. WHEN a user dismisses a notification, THE Mail_System SHALL set is_dismissed to True for that notification
2. WHEN a user requests their notifications, THE Mail_System SHALL return notifications ordered by created_at descending
3. WHEN a user requests unread notifications, THE Mail_System SHALL filter to notifications where is_dismissed is False
4. WHEN a user dismisses all notifications, THE Mail_System SHALL set is_dismissed to True for all of the user's notifications
5. THE Mail_System SHALL support filtering notifications by notification_type

### Requirement 11: Inbox Retrieval and Filtering

**User Story:** As an ERP user, I want to retrieve my inbox with filtering options, so that I can find specific messages efficiently.

#### Acceptance Criteria

1. WHEN a user requests their inbox, THE Mail_System SHALL return all Recipient_Record entries where recipient equals the user and is_deleted is False
2. WHEN a user applies an is_read filter, THE Mail_System SHALL return only messages matching the specified read state
3. WHEN a user applies an is_archived filter, THE Mail_System SHALL return only messages matching the specified archived state
4. WHEN a user applies a folder_label filter, THE Mail_System SHALL return only messages with the specified folder label
5. WHEN a user applies a search query, THE Mail_System SHALL search across message subject, body, and sender username
6. WHEN a user requests their inbox, THE Mail_System SHALL order results by message sent_at descending
7. WHEN a user requests their inbox, THE Mail_System SHALL use select_related and prefetch_related to optimize database queries
8. WHEN a user requests their inbox, THE Mail_System SHALL support pagination with a default page size of 50 messages

### Requirement 12: Sent Messages Retrieval

**User Story:** As an ERP user, I want to view messages I have sent, so that I can track my outgoing communications.

#### Acceptance Criteria

1. WHEN a user requests their sent messages, THE Mail_System SHALL return all Message records where sender equals the user and status is 'SENT'
2. WHEN a user requests their sent messages, THE Mail_System SHALL order results by sent_at descending
3. WHEN a user requests their sent messages, THE Mail_System SHALL include the count of recipients for each message
4. WHEN a user requests their sent messages, THE Mail_System SHALL include the count of attached resources for each message
5. WHEN a user requests their sent messages, THE Mail_System SHALL support pagination

### Requirement 13: Message Threading and Replies

**User Story:** As an ERP user, I want to reply to messages and maintain conversation threads, so that related communications are grouped together.

#### Acceptance Criteria

1. WHEN a user creates a reply to a message, THE Mail_System SHALL set parent_message to reference the original message
2. WHEN a user creates a reply, THE Mail_System SHALL verify that the original message has status 'SENT'
3. WHEN a user creates a reply, THE Mail_System SHALL verify that the user is either the original sender or a recipient of the original message
4. WHEN a user creates a reply, THE Mail_System SHALL prefix the subject with "Re: " if not already present
5. WHEN a user requests a message thread, THE Mail_System SHALL return all messages with the same parent_message reference
6. WHEN a reply is sent, THE Mail_System SHALL create notifications with type 'NEW_REPLY' instead of 'NEW_MESSAGE'

### Requirement 14: Soft Delete and Restore

**User Story:** As an ERP user, I want to delete messages from my inbox with the ability to restore them, so that I can recover accidentally deleted messages.

#### Acceptance Criteria

1. WHEN a recipient deletes a message, THE Mail_System SHALL set is_deleted to True on the Recipient_Record
2. WHEN a recipient deletes a message, THE Mail_System SHALL set deleted_at to the current timestamp
3. WHEN a recipient deletes a message, THE Mail_System SHALL retain the Recipient_Record in the database
4. WHEN a recipient deletes a message, THE Mail_System SHALL exclude it from inbox queries
5. WHEN a recipient restores a deleted message, THE Mail_System SHALL set is_deleted to False and deleted_at to NULL
6. WHEN a sender deletes a Draft, THE Mail_System SHALL set the message status to 'DELETED_BY_SENDER'
7. WHEN a sender deletes a Sent_Message, THE Mail_System SHALL set the message status to 'DELETED_BY_SENDER' without affecting recipients' access

### Requirement 15: Resource Navigation URL Generation

**User Story:** As a message recipient, I want to click on attached resources and navigate directly to them in the ERP, so that I can view the full resource details.

#### Acceptance Criteria

1. WHEN a recipient clicks on a Resource_Widget, THE Mail_System SHALL generate a navigation URL in the format `/app/{module}/{resource_type}/{resource_id}`
2. WHEN generating a resource URL, THE Mail_System SHALL use the content_type and object_id from the MessageResource record
3. WHEN generating a resource URL, THE Mail_System SHALL verify the resource still exists before returning the URL
4. WHEN a resource no longer exists, THE Mail_System SHALL return an error indicating the resource is unavailable
5. WHEN a recipient lacks access to a resource, THE Mail_System SHALL prevent URL generation and display an access denied message

### Requirement 16: BCC Privacy Protection

**User Story:** As a message sender, I want BCC recipients to be hidden from TO and CC recipients, so that I can send blind copies without revealing those recipients.

#### Acceptance Criteria

1. WHEN a message is sent with BCC recipients, THE Mail_System SHALL store BCC recipient records with recipient_type 'BCC'
2. WHEN a TO or CC recipient views a message, THE Mail_System SHALL exclude BCC recipients from the displayed recipient list
3. WHEN a BCC recipient views a message, THE Mail_System SHALL display all recipients including other BCC recipients
4. WHEN a message is sent with BCC recipients, THE Mail_System SHALL create notifications for BCC recipients
5. WHEN a recipient replies to a message, THE Mail_System SHALL not include BCC recipients from the original message in the reply recipients

### Requirement 17: Message Status Transitions

**User Story:** As a system administrator, I want message status to follow a controlled lifecycle, so that message state transitions are predictable and auditable.

#### Acceptance Criteria

1. WHEN a message is created, THE Mail_System SHALL initialize status to 'DRAFT'
2. WHEN a Draft is sent, THE Mail_System SHALL transition status from 'DRAFT' to 'SENT'
3. WHEN a sender deletes a message, THE Mail_System SHALL transition status to 'DELETED_BY_SENDER'
4. THE Mail_System SHALL not allow status transitions from 'SENT' back to 'DRAFT'
5. THE Mail_System SHALL not allow status transitions from 'DELETED_BY_SENDER' to any other status
6. WHEN a message status is 'SENT', THE Mail_System SHALL ensure sent_at is not NULL

### Requirement 18: Audit Trail Preservation

**User Story:** As a compliance officer, I want message audit trails to be preserved even when users are deleted, so that we maintain complete communication history.

#### Acceptance Criteria

1. WHEN a sender user is deleted, THE Mail_System SHALL preserve the Message record with the sender reference intact
2. WHEN a recipient user is deleted, THE Mail_System SHALL preserve the Recipient_Record with the recipient reference intact
3. WHEN a user who attached a resource is deleted, THE Mail_System SHALL preserve the MessageResource record with the attached_by reference intact
4. THE Mail_System SHALL use PROTECT deletion behavior on sender, recipient, and attached_by foreign keys
5. WHEN a message is deleted, THE Mail_System SHALL use CASCADE deletion behavior to remove associated Recipient_Record and MessageResource records
6. THE Mail_System SHALL preserve created_at, sent_at, read_at, and deleted_at timestamps for audit purposes

### Requirement 19: Database Indexing for Performance

**User Story:** As a system administrator, I want optimized database queries for common operations, so that the mail system performs efficiently at scale.

#### Acceptance Criteria

1. THE Mail_System SHALL create a composite index on Message (sender, status)
2. THE Mail_System SHALL create an index on Message (parent_message)
3. THE Mail_System SHALL create an index on Message (sent_at)
4. THE Mail_System SHALL create a composite index on MessageRecipient (recipient, is_read)
5. THE Mail_System SHALL create a composite index on MessageRecipient (recipient, is_deleted)
6. THE Mail_System SHALL create a composite index on MessageRecipient (recipient, is_archived)
7. THE Mail_System SHALL create an index on MessageResource (message)
8. THE Mail_System SHALL create a composite index on MessageResource (content_type, object_id)
9. THE Mail_System SHALL create a composite index on MailNotification (recipient, is_dismissed)
10. THE Mail_System SHALL create an index on MailNotification (created_at)

### Requirement 20: Rate Limiting and Spam Prevention

**User Story:** As a system administrator, I want rate limiting on message sending, so that the system is protected from spam and abuse.

#### Acceptance Criteria

1. THE Mail_System SHALL limit each user to a maximum of 100 sent messages per hour
2. WHEN a user exceeds the rate limit, THE Mail_System SHALL reject the send operation and return a rate limit error
3. THE Mail_System SHALL limit each message to a maximum of 50 recipients
4. WHEN a user attempts to send to more than 50 recipients, THE Mail_System SHALL reject the operation
5. THE Mail_System SHALL detect when a user sends the same message body to many different recipients within a short time period
6. WHEN suspicious spam patterns are detected, THE Mail_System SHALL flag the messages for review

### Requirement 21: Architectural Independence

**User Story:** As a system architect, I want the mail service to be architecturally independent from other ERP modules, so that it can be maintained and evolved separately.

#### Acceptance Criteria

1. THE Mail_System SHALL import models from purchasing, production, inventory, sales, costing, finance, and accounting modules
2. THE Mail_System SHALL not be imported by any other ERP module
3. WHEN other modules need mail functionality, THE Mail_System SHALL provide a service layer API
4. THE Mail_System SHALL use Django ContentType framework for polymorphic resource relationships
5. THE Mail_System SHALL not create foreign keys from other modules to mail models

### Requirement 22: Data Retention and Cleanup

**User Story:** As a system administrator, I want automated cleanup of old data, so that the database does not grow unbounded.

#### Acceptance Criteria

1. THE Mail_System SHALL provide a periodic job to hard-delete messages soft-deleted more than 90 days ago
2. THE Mail_System SHALL provide a periodic job to delete dismissed notifications older than 30 days
3. THE Mail_System SHALL provide a periodic job to archive messages older than 1 year to a separate table
4. THE Mail_System SHALL retain all sent messages for a minimum of 7 years for compliance
5. THE Mail_System SHALL support legal hold functionality to prevent deletion of specific messages

### Requirement 23: Search Functionality

**User Story:** As an ERP user, I want to search my messages by content and metadata, so that I can quickly find specific communications.

#### Acceptance Criteria

1. WHEN a user performs a search, THE Mail_System SHALL search across message subject and body fields
2. WHEN a user performs a search, THE Mail_System SHALL search across sender username
3. WHEN a user performs a search, THE Mail_System SHALL use case-insensitive matching
4. WHEN a user performs a search, THE Mail_System SHALL limit search query length to 200 characters
5. WHEN a user performs a search, THE Mail_System SHALL sanitize input to prevent SQL injection
6. WHEN a user performs a search, THE Mail_System SHALL return results ordered by relevance and recency
7. THE Mail_System SHALL complete search queries in less than 1 second for up to 10,000 messages

### Requirement 24: Folder Organization

**User Story:** As an ERP user, I want to organize messages into custom folders, so that I can categorize my communications.

#### Acceptance Criteria

1. WHEN a recipient assigns a folder label to a message, THE Mail_System SHALL store it in the folder_label field of the Recipient_Record
2. THE Mail_System SHALL limit folder_label to 50 characters
3. THE Mail_System SHALL validate that folder_label contains only alphanumeric characters, hyphens, and underscores
4. WHEN a recipient filters by folder, THE Mail_System SHALL return only messages with the specified folder_label
5. WHEN a recipient removes a folder label, THE Mail_System SHALL set folder_label to NULL

### Requirement 25: Performance Targets

**User Story:** As a system administrator, I want the mail system to meet specific performance targets, so that users have a responsive experience.

#### Acceptance Criteria

1. THE Mail_System SHALL retrieve an inbox of 50 messages in less than 200 milliseconds
2. THE Mail_System SHALL complete message send operations in less than 500 milliseconds including notification creation
3. THE Mail_System SHALL attach a resource to a message in less than 100 milliseconds
4. THE Mail_System SHALL complete full-text search queries in less than 1 second for 10,000 messages
5. THE Mail_System SHALL use database query optimization techniques including select_related and prefetch_related

### Requirement 26: Input Validation and Security

**User Story:** As a security engineer, I want comprehensive input validation, so that the system is protected from injection attacks and malformed data.

#### Acceptance Criteria

1. WHEN a user provides a subject, THE Mail_System SHALL validate it is non-empty and maximum 255 characters
2. WHEN a user provides a body, THE Mail_System SHALL validate it is non-empty and maximum 10,000 characters
3. WHEN a user provides a recipient list, THE Mail_System SHALL validate all user IDs are valid UUIDs
4. WHEN a user provides a resource ID, THE Mail_System SHALL validate it is a valid UUID
5. WHEN a user provides a search query, THE Mail_System SHALL sanitize it to prevent SQL injection
6. WHEN a user provides HTML content in the body, THE Mail_System SHALL sanitize it to prevent XSS attacks
7. THE Mail_System SHALL use parameterized queries for all database operations

### Requirement 27: Real-Time Notification Delivery

**User Story:** As an ERP user, I want to receive real-time notifications when new messages arrive, so that I can respond promptly to communications.

#### Acceptance Criteria

1. WHEN a message is sent, THE Mail_System SHALL trigger asynchronous notification delivery
2. THE Mail_System SHALL use WebSocket connections for real-time notification push
3. WHEN a recipient is online, THE Mail_System SHALL deliver notifications within 2 seconds of message send
4. WHEN a recipient is offline, THE Mail_System SHALL queue notifications for delivery when they reconnect
5. THE Mail_System SHALL support optional email notifications for new messages
6. THE Mail_System SHALL support optional desktop push notifications

### Requirement 28: Message Uniqueness and Deduplication

**User Story:** As a system administrator, I want to prevent duplicate recipient records, so that data integrity is maintained.

#### Acceptance Criteria

1. THE Mail_System SHALL enforce a unique constraint on (message, recipient) in the MessageRecipient table
2. WHEN a user attempts to add the same recipient twice to a message, THE Mail_System SHALL reject the duplicate
3. WHEN a message is sent, THE Mail_System SHALL create exactly one Recipient_Record per unique recipient
4. THE Mail_System SHALL allow the same user to appear as different recipient types (TO, CC, BCC) by treating them as separate recipients

### Requirement 29: Resource Attachment Limits

**User Story:** As a system administrator, I want limits on resource attachments per message, so that messages remain manageable and performant.

#### Acceptance Criteria

1. THE Mail_System SHALL allow a maximum of 20 resources to be attached to a single message
2. WHEN a user attempts to attach more than 20 resources, THE Mail_System SHALL reject the operation
3. THE Mail_System SHALL prevent attaching the same resource multiple times to the same message
4. WHEN a user attempts to attach a duplicate resource, THE Mail_System SHALL reject the operation

### Requirement 30: Caching Strategy

**User Story:** As a system administrator, I want strategic caching of frequently accessed data, so that system performance is optimized.

#### Acceptance Criteria

1. THE Mail_System SHALL cache each user's unread message count with a TTL of 5 minutes
2. THE Mail_System SHALL cache the SHAREABLE_RESOURCES whitelist configuration with a TTL of 1 hour
3. THE Mail_System SHALL cache user role and warehouse access information with a TTL of 15 minutes
4. THE Mail_System SHALL not cache resource labels as they are immutable after send
5. THE Mail_System SHALL invalidate cached unread counts when a user marks messages as read
