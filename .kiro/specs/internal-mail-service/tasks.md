# Implementation Plan: Internal Mail Service

## Overview

This implementation plan breaks down the Internal Mail Service feature into discrete, actionable coding tasks. The service enables cross-module communication with live ERP resource attachments, treating shared resources as interactive widgets. The implementation follows a layered approach: models → service layer → API endpoints → notifications → testing. Each task builds incrementally on previous work, with checkpoints to ensure stability.

## Tasks

- [ ] 1. Set up project structure and core configuration
  - Create `backend/apps/mail/` directory structure (models, services, serializers, views)
  - Create `backend/apps/mail/constants.py` for SHAREABLE_RESOURCES whitelist
  - Configure Django app in `backend/apps/mail/apps.py`
  - Add mail app to `INSTALLED_APPS` in settings
  - Set up URL routing in `backend/apps/mail/urls.py`
  - _Requirements: 21.1, 21.2, 21.4_

- [ ] 2. Implement core data models
  - [ ] 2.1 Create Message model
    - Implement Message model with all fields (id, sender, subject, body, status, parent_message, is_draft, sent_at, created_at, updated_at)
    - Add STATUS_CHOICES and validation logic
    - Implement model methods: `send()`, `can_edit()`, `get_recipients()`, `get_resources()`
    - Add database indexes: `(sender, status)`, `(parent_message)`, `(sent_at)`
    - Configure Meta class with ordering and verbose names
    - _Requirements: 1.1-1.7, 2.1-2.7, 17.1-17.6_
  
  - [ ]* 2.2 Write property test for Message immutability
    - **Property 1: Message Immutability After Sending**
    - **Validates: Requirements 2.5, 4.1**
    - Test that once `is_draft=False`, subject and body cannot be modified
  
  - [ ] 2.3 Create MessageRecipient model
    - Implement MessageRecipient model with all fields (id, message, recipient, recipient_type, is_read, read_at, is_archived, is_deleted, deleted_at, folder_label, created_at)
    - Add RECIPIENT_TYPE_CHOICES
    - Implement model methods: `mark_as_read()`, `mark_as_unread()`, `archive()`, `unarchive()`, `soft_delete()`, `restore()`
    - Add database indexes: `(recipient, is_read)`, `(recipient, is_deleted)`, `(recipient, is_archived)`
    - Add unique_together constraint on `(message, recipient)`
    - _Requirements: 3.1-3.6, 4.1-4.7, 14.1-14.7_
  
  - [ ]* 2.4 Write property test for recipient state independence
    - **Property 2: Recipient State Independence**
    - **Validates: Requirements 4.6**
    - Test that each recipient's state (is_read, is_archived, is_deleted) is independent of other recipients
  
  - [ ] 2.5 Create MessageResource model
    - Implement MessageResource model with ContentType framework (id, message, content_type, object_id, content_object, resource_label, resource_type_display, attached_by, created_at, access_verified_at)
    - Implement model methods: `get_resource()`, `verify_access()`, `get_resource_url()`, `refresh_label()`
    - Add database indexes: `(message)`, `(content_type, object_id)`
    - _Requirements: 5.1-5.9, 6.1-6.8, 7.1-7.4, 8.1-8.10_
  
  - [ ]* 2.6 Write property test for resource whitelist enforcement
    - **Property 3: Resource Whitelist Enforcement**
    - **Validates: Requirements 5.1, 8.10**
    - Test that all attached resources must be in SHAREABLE_RESOURCES whitelist
  
  - [ ] 2.7 Create MailNotification model
    - Implement MailNotification model with all fields (id, recipient, message, notification_type, is_dismissed, created_at)
    - Add NOTIFICATION_TYPE_CHOICES
    - Implement model methods: `dismiss()`, `get_notification_text()`
    - Add database indexes: `(recipient, is_dismissed)`, `(created_at)`
    - _Requirements: 9.1-9.7, 10.1-10.5_

- [ ] 3. Create and run initial database migrations
  - Generate Django migrations for all models
  - Review migration files for correctness
  - Run migrations on development database
  - Verify all tables, indexes, and constraints are created
  - _Requirements: 19.1-19.10_

- [ ] 4. Checkpoint - Verify models and database schema
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement SHAREABLE_RESOURCES whitelist configuration
  - [ ] 5.1 Define SHAREABLE_RESOURCES constant in constants.py
    - Add all 32 resource types across 7 modules (Purchasing: 6, Production: 3, Inventory: 5, Sales: 5, Costing: 5, Finance: 3, Accounting: 1, Central: 2)
    - For each resource type, define: model path, label_fields, display_name
    - _Requirements: 8.1-8.10_
  
  - [ ]* 5.2 Write unit tests for whitelist configuration
    - Test that all 32 resource types are present
    - Test that each resource type has required fields (model, label_fields, display_name)
    - _Requirements: 8.1-8.10_

- [ ] 6. Implement MailService layer
  - [ ] 6.1 Create MailService class with draft creation
    - Implement `create_draft()` method with validation
    - Validate subject (non-empty, max 255 chars) and body (non-empty, max 10,000 chars)
    - Validate recipients (at least one, all valid and active users)
    - Support parent_message for threading
    - _Requirements: 1.1-1.7, 13.1-13.6, 26.1-26.7_
  
  - [ ]* 6.2 Write unit tests for create_draft
    - Test draft creation with valid data
    - Test validation errors for invalid subject/body
    - Test validation errors for invalid recipients
    - _Requirements: 1.1-1.7_
  
  - [ ] 6.3 Implement send_message() method
    - Validate message is in DRAFT status
    - Transition message to SENT status (set is_draft=False, sent_at=now())
    - Create MessageRecipient records for all recipients
    - Create MailNotification records for all recipients
    - Use atomic transaction for consistency
    - _Requirements: 2.1-2.7, 9.1-9.7_
  
  - [ ]* 6.4 Write property test for sent message completeness
    - **Property 5: Sent Message Completeness**
    - **Validates: Requirements 2.1-2.7**
    - Test that all sent messages have sent_at, is_draft=False, and at least one recipient
  
  - [ ] 6.5 Implement attach_resource() method
    - Validate message is in DRAFT status
    - Validate resource type is in SHAREABLE_RESOURCES whitelist
    - Validate resource object exists
    - Verify user has access to resource
    - Generate resource_label from label_fields
    - Create MessageResource record
    - Enforce maximum 20 resources per message
    - _Requirements: 5.1-5.9, 29.1-29.4_
  
  - [ ]* 6.6 Write property test for resource access verification
    - **Property 4: Access Verification Requirement**
    - **Validates: Requirements 6.1-6.8**
    - Test that users can only attach resources they have permission to access
  
  - [ ] 6.7 Implement verify_resource_access() method
    - Implement role-based access control for each resource type
    - Handle PurchaseOrder access (purchasing roles or creator)
    - Handle ProductionOrder access (production roles or warehouse match)
    - Handle StockMovement access (inventory roles or warehouse match)
    - Handle Invoice access (sales/accounting roles or creator)
    - Default to manager/admin access for all resources
    - _Requirements: 6.1-6.8_
  
  - [ ]* 6.8 Write unit tests for verify_resource_access
    - Test access control for different user roles
    - Test warehouse-based access restrictions
    - Test creator-based access
    - _Requirements: 6.1-6.8_
  
  - [ ] 6.9 Implement get_inbox() method
    - Query MessageRecipient records for user where is_deleted=False
    - Support filtering by is_read, is_archived, folder_label
    - Support search across subject, body, sender username
    - Use select_related and prefetch_related for optimization
    - Order by message.sent_at descending
    - Support pagination (default 50 per page)
    - _Requirements: 11.1-11.8, 23.1-23.7, 25.1_
  
  - [ ]* 6.10 Write property test for inbox query correctness
    - **Property 10: Inbox Query Correctness**
    - **Validates: Requirements 11.1-11.8**
    - Test that inbox queries return only user's non-deleted messages matching all filters
  
  - [ ] 6.11 Implement get_sent_messages() method
    - Query Message records where sender=user and status='SENT'
    - Include recipient count and resource count
    - Order by sent_at descending
    - Support pagination
    - _Requirements: 12.1-12.5_
  
  - [ ] 6.12 Implement reply_to_message() method
    - Validate original message is SENT
    - Validate sender is original sender or recipient
    - Prefix subject with "Re: " if not present
    - Create draft with parent_message reference
    - _Requirements: 13.1-13.6_
  
  - [ ]* 6.13 Write property test for thread consistency
    - **Property 8: Thread Consistency**
    - **Validates: Requirements 13.1-13.6**
    - Test that replies reference sent messages and sender is authorized
  
  - [ ] 6.14 Implement mark_as_read() and state management methods
    - Implement mark_as_read() to set is_read=True and read_at=now()
    - Implement mark_as_unread() to set is_read=False and read_at=None
    - Implement archive() and unarchive() methods
    - Implement soft_delete() and restore() methods
    - _Requirements: 4.1-4.7, 14.1-14.7_
  
  - [ ]* 6.15 Write property test for soft delete preservation
    - **Property 7: Soft Delete Preservation**
    - **Validates: Requirements 14.1-14.7**
    - Test that soft-deleted messages remain in database with deletion timestamp

- [ ] 7. Checkpoint - Verify service layer functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement serializers
  - [ ] 8.1 Create MessageSerializer
    - Serialize all Message fields
    - Include nested sender information
    - Include recipient count and resource count
    - Handle read-only fields (sent_at, created_at, updated_at)
    - _Requirements: 1.1-1.7, 2.1-2.7_
  
  - [ ] 8.2 Create MessageRecipientSerializer
    - Serialize all MessageRecipient fields
    - Include nested message and recipient information
    - Handle read-only fields (read_at, deleted_at, created_at)
    - _Requirements: 3.1-3.6, 4.1-4.7_
  
  - [ ] 8.3 Create MessageResourceSerializer
    - Serialize all MessageResource fields
    - Include resource_url generation
    - Handle ContentType serialization
    - _Requirements: 5.1-5.9, 15.1-15.5_
  
  - [ ] 8.4 Create MailNotificationSerializer
    - Serialize all MailNotification fields
    - Include notification_text generation
    - Handle read-only fields (created_at)
    - _Requirements: 9.1-9.7, 10.1-10.5_
  
  - [ ] 8.5 Create request/response serializers
    - Create MessageCreateSerializer for draft creation
    - Create MessageSendSerializer for sending messages
    - Create ResourceAttachSerializer for resource attachment
    - Create InboxFilterSerializer for inbox filtering
    - Create ReplySerializer for message replies
    - _Requirements: 1.1-1.7, 2.1-2.7, 5.1-5.9, 11.1-11.8, 13.1-13.6_
  
  - [ ]* 8.6 Write unit tests for serializers
    - Test serialization and deserialization
    - Test validation logic
    - Test nested relationships
    - _Requirements: 26.1-26.7_

- [ ] 9. Implement API views and endpoints
  - [ ] 9.1 Create MessageViewSet
    - Implement list action (GET /api/mail/messages/) for sent messages
    - Implement retrieve action (GET /api/mail/messages/{id}/)
    - Implement create action (POST /api/mail/messages/) for draft creation
    - Implement partial_update action (PATCH /api/mail/messages/{id}/) for draft editing
    - Implement destroy action (DELETE /api/mail/messages/{id}/) for draft deletion
    - Add custom action send (POST /api/mail/messages/{id}/send/)
    - Add custom action reply (POST /api/mail/messages/{id}/reply/)
    - Add custom action thread (GET /api/mail/messages/{id}/thread/)
    - Add permission checks and company scoping
    - _Requirements: 1.1-1.7, 2.1-2.7, 12.1-12.5, 13.1-13.6_
  
  - [ ] 9.2 Create InboxViewSet
    - Implement list action (GET /api/mail/inbox/) with filtering
    - Implement retrieve action (GET /api/mail/inbox/{id}/)
    - Implement partial_update action (PATCH /api/mail/inbox/{id}/) for state updates
    - Implement destroy action (DELETE /api/mail/inbox/{id}/) for soft delete
    - Add custom action restore (POST /api/mail/inbox/{id}/restore/)
    - Add filtering by is_read, is_archived, folder_label, search_query
    - Add pagination support
    - _Requirements: 11.1-11.8, 14.1-14.7, 23.1-23.7, 24.1-24.5_
  
  - [ ] 9.3 Create MessageResourceViewSet
    - Implement list action (GET /api/mail/messages/{message_id}/resources/)
    - Implement create action (POST /api/mail/messages/{message_id}/resources/)
    - Implement destroy action (DELETE /api/mail/messages/{message_id}/resources/{id}/)
    - Add custom action get_url (GET /api/mail/resources/{id}/url/)
    - Add access verification before returning URLs
    - _Requirements: 5.1-5.9, 6.1-6.8, 15.1-15.5_
  
  - [ ] 9.4 Create MailNotificationViewSet
    - Implement list action (GET /api/mail/notifications/) with filtering
    - Implement retrieve action (GET /api/mail/notifications/{id}/)
    - Add custom action dismiss (PATCH /api/mail/notifications/{id}/dismiss/)
    - Add custom action dismiss_all (POST /api/mail/notifications/dismiss-all/)
    - Add filtering by is_dismissed, notification_type
    - _Requirements: 9.1-9.7, 10.1-10.5_
  
  - [ ]* 9.5 Write integration tests for API endpoints
    - Test complete message flow: create draft → attach resources → send → receive
    - Test inbox filtering and pagination
    - Test resource attachment and access verification
    - Test notification creation and dismissal
    - Test error responses for invalid operations
    - _Requirements: 1.1-1.7, 2.1-2.7, 5.1-5.9, 9.1-9.7, 11.1-11.8_

- [ ] 10. Implement rate limiting and spam prevention
  - [ ] 10.1 Add rate limiting middleware
    - Implement rate limiter for message sending (100 messages per hour per user)
    - Implement rate limiter for recipient count (max 50 per message)
    - Return appropriate error responses when limits exceeded
    - _Requirements: 20.1-20.6_
  
  - [ ]* 10.2 Write unit tests for rate limiting
    - Test rate limit enforcement
    - Test error responses
    - _Requirements: 20.1-20.6_

- [ ] 11. Checkpoint - Verify API functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement notification delivery system
  - [ ] 12.1 Set up Celery for async task processing
    - Configure Celery with Redis broker
    - Create Celery app configuration
    - Set up Celery workers
    - _Requirements: 27.1-27.6_
  
  - [ ] 12.2 Create notification delivery tasks
    - Implement async task for creating notifications on message send
    - Implement async task for WebSocket notification push
    - Implement async task for optional email notifications
    - Handle notification queuing for offline users
    - _Requirements: 9.1-9.7, 27.1-27.6_
  
  - [ ]* 12.3 Write unit tests for notification tasks
    - Test notification creation
    - Test notification delivery
    - Test offline user queuing
    - _Requirements: 9.1-9.7, 27.1-27.6_

- [ ] 13. Implement WebSocket support for real-time notifications
  - [ ] 13.1 Set up Django Channels
    - Configure Channels with Redis channel layer
    - Create ASGI application configuration
    - Set up WebSocket routing
    - _Requirements: 27.1-27.6_
  
  - [ ] 13.2 Create WebSocket consumers
    - Implement MailNotificationConsumer for real-time push
    - Handle WebSocket connection/disconnection
    - Implement notification broadcasting to connected users
    - _Requirements: 27.1-27.6_
  
  - [ ]* 13.3 Write integration tests for WebSocket notifications
    - Test WebSocket connection and authentication
    - Test real-time notification delivery
    - Test notification delivery within 2 seconds
    - _Requirements: 27.1-27.6_

- [ ] 14. Implement caching strategy
  - [ ] 14.1 Add caching for frequently accessed data
    - Cache unread message count per user (TTL: 5 minutes)
    - Cache SHAREABLE_RESOURCES whitelist (TTL: 1 hour)
    - Cache user role and warehouse access (TTL: 15 minutes)
    - Implement cache invalidation on state changes
    - _Requirements: 30.1-30.5_
  
  - [ ]* 14.2 Write unit tests for caching
    - Test cache hit/miss behavior
    - Test cache invalidation
    - Test TTL expiration
    - _Requirements: 30.1-30.5_

- [ ] 15. Implement data retention and cleanup jobs
  - [ ] 15.1 Create periodic cleanup tasks
    - Implement task to hard-delete messages soft-deleted >90 days ago
    - Implement task to delete dismissed notifications >30 days old
    - Implement task to archive messages >1 year old
    - Ensure 7-year retention for compliance
    - Implement legal hold functionality
    - _Requirements: 22.1-22.5_
  
  - [ ]* 15.2 Write unit tests for cleanup tasks
    - Test deletion logic
    - Test retention periods
    - Test legal hold functionality
    - _Requirements: 22.1-22.5_

- [ ] 16. Implement BCC privacy protection
  - [ ] 16.1 Add BCC filtering logic
    - Filter BCC recipients from recipient list for TO/CC recipients
    - Show all recipients including BCC to BCC recipients
    - Exclude BCC recipients from reply recipient lists
    - _Requirements: 16.1-16.5_
  
  - [ ]* 16.2 Write unit tests for BCC privacy
    - Test BCC recipient visibility
    - Test BCC exclusion from replies
    - _Requirements: 16.1-16.5_

- [ ] 17. Implement input validation and security
  - [ ] 17.1 Add comprehensive input validation
    - Validate subject length (max 255 chars)
    - Validate body length (max 10,000 chars)
    - Validate recipient UUIDs
    - Validate resource UUIDs
    - Sanitize search queries to prevent SQL injection
    - Sanitize HTML content to prevent XSS
    - Use parameterized queries for all database operations
    - _Requirements: 26.1-26.7_
  
  - [ ]* 17.2 Write security tests
    - Test SQL injection prevention
    - Test XSS prevention
    - Test input validation
    - _Requirements: 26.1-26.7_

- [ ] 18. Checkpoint - Verify complete system functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 19. Performance optimization and verification
  - [ ] 19.1 Verify database query optimization
    - Verify select_related and prefetch_related usage in inbox queries
    - Verify all required indexes are created
    - Run query analysis to identify N+1 queries
    - _Requirements: 19.1-19.10, 25.1-25.5_
  
  - [ ] 19.2 Run performance benchmarks
    - Verify inbox retrieval <200ms for 50 messages
    - Verify message send <500ms including notifications
    - Verify resource attachment <100ms
    - Verify search queries <1s for 10,000 messages
    - _Requirements: 25.1-25.5_
  
  - [ ]* 19.3 Write performance tests
    - Test inbox query performance
    - Test message send performance
    - Test search performance
    - _Requirements: 25.1-25.5_

- [ ] 20. Final integration and wiring
  - [ ] 20.1 Wire all components together
    - Verify URL routing is complete
    - Verify all API endpoints are accessible
    - Verify WebSocket connections work
    - Verify Celery tasks are running
    - Verify caching is working
    - _Requirements: All_
  
  - [ ] 20.2 Create API documentation
    - Document all endpoints with request/response examples
    - Document error codes and responses
    - Document WebSocket protocol
    - _Requirements: All_
  
  - [ ]* 20.3 Write end-to-end integration tests
    - Test complete user workflows
    - Test cross-module resource attachment
    - Test concurrent access scenarios
    - Test permission boundaries
    - _Requirements: All_

- [ ] 21. Final checkpoint - Complete system verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- The implementation uses Python with Django and Django REST Framework
- All code should follow Django best practices and the existing project structure
- Use atomic transactions for operations that modify multiple records
- Use select_related and prefetch_related for query optimization
- Follow the existing project patterns for views, serializers, and services
