"""Master Spec alignment - Add enterprise features

Revision ID: 20260112_master_spec
Revises: 6a46bc2e4680
Create Date: 2026-01-12

This migration aligns the database with the FreightOps HQ Master System Architecture:
- Module 1: Lead Engine (PQL scoring, enrichment status, lead locking)
- Module 2: Tenant Management (hardship pause, impersonation, hierarchy)
- Module 3: Embedded Finance (MRR tracking, banking/payroll status)
- Module 4: Affiliate & Sales (referral codes, commission tracking)
- Module 5: AI Monitoring (token usage, cost tracking)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260112_master_spec'
down_revision = '6a46bc2e4680'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # Module 1: Lead Engine Enhancements
    # ========================================================================

    # Create enrichment status enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'enrichmentstatus') THEN
                CREATE TYPE enrichmentstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED');
            END IF;
        END $$;
    """)

    # Add PQL score and enrichment status to hq_deal
    op.add_column('hq_deal', sa.Column('pql_score', sa.Numeric(3, 2), nullable=True, comment='Product Qualified Lead score 0.00-1.00'))
    op.add_column('hq_deal', sa.Column('pql_scored_at', sa.DateTime(), nullable=True, comment='When PQL scoring was last calculated'))
    op.add_column('hq_deal', sa.Column('pql_factors', sa.Text(), nullable=True, comment='JSON explaining PQL score factors'))
    op.add_column('hq_deal', sa.Column(
        'enrichment_status',
        postgresql.ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', name='enrichmentstatus'),
        nullable=True,
        server_default='PENDING',
        comment='Enrichment workflow status'
    ))
    op.add_column('hq_deal', sa.Column('enrichment_attempted_at', sa.DateTime(), nullable=True, comment='When enrichment was last attempted'))
    op.add_column('hq_deal', sa.Column('enrichment_completed_at', sa.DateTime(), nullable=True, comment='When enrichment successfully completed'))

    # Add lead locking fields
    op.add_column('hq_deal', sa.Column('claimed_by_id', sa.String(), nullable=True, comment='Sales rep who claimed this lead'))
    op.add_column('hq_deal', sa.Column('claimed_at', sa.DateTime(), nullable=True, comment='When the lead was claimed'))
    op.add_column('hq_deal', sa.Column('claim_expires_at', sa.DateTime(), nullable=True, comment='When the 30-day claim expires'))
    op.create_foreign_key('fk_hq_deal_claimed_by', 'hq_deal', 'hq_employee', ['claimed_by_id'], ['id'])
    op.create_index('ix_hq_deal_pql_score', 'hq_deal', ['pql_score'])
    op.create_index('ix_hq_deal_enrichment_status', 'hq_deal', ['enrichment_status'])
    op.create_index('ix_hq_deal_claimed_by', 'hq_deal', ['claimed_by_id'])

    # Add time-to-first-contact tracking
    op.add_column('hq_deal', sa.Column('first_contact_at', sa.DateTime(), nullable=True, comment='First meaningful contact timestamp'))
    op.add_column('hq_deal', sa.Column('time_to_first_contact_hours', sa.Numeric(10, 2), nullable=True, comment='Hours from creation to first contact'))

    # ========================================================================
    # Module 2: Tenant Management Enhancements
    # ========================================================================

    # Create new subscription_status enum with hardship pause
    # Drop if exists and recreate to ensure correct values
    op.execute("""
        DO $$ BEGIN
            -- Drop enum if it exists
            DROP TYPE IF EXISTS subscriptionstatus CASCADE;

            -- Create with correct values
            CREATE TYPE subscriptionstatus AS ENUM (
                'ACTIVE',
                'TRIALING',
                'PAUSED_HARDSHIP',
                'CANCELLED',
                'DELINQUENT',
                'PAST_DUE'
            );
        END $$;
    """)

    # Add enhanced subscription status to hq_tenant
    op.add_column('hq_tenant', sa.Column(
        'subscription_status',
        postgresql.ENUM('ACTIVE', 'TRIALING', 'PAUSED_HARDSHIP', 'CANCELLED', 'DELINQUENT', 'PAST_DUE', name='subscriptionstatus'),
        nullable=True,
        server_default='TRIALING',
        comment='Enhanced subscription status'
    ))

    # Add hardship pause tracking
    op.add_column('hq_tenant', sa.Column('paused_at', sa.DateTime(), nullable=True, comment='When hardship pause started'))
    op.add_column('hq_tenant', sa.Column('pause_reason', sa.Text(), nullable=True, comment='Reason for hardship pause'))
    op.add_column('hq_tenant', sa.Column('pause_expires_at', sa.DateTime(), nullable=True, comment='When pause automatically expires'))
    op.add_column('hq_tenant', sa.Column('paused_by_id', sa.String(), nullable=True, comment='HQ employee who approved pause'))
    op.create_foreign_key('fk_hq_tenant_paused_by', 'hq_tenant', 'hq_employee', ['paused_by_id'], ['id'])

    # Add tenant hierarchy and referral tracking
    op.add_column('hq_tenant', sa.Column('referred_by_agent_id', sa.String(), nullable=True, comment='Sales agent who referred this tenant'))
    op.add_column('hq_tenant', sa.Column('referral_code_used', sa.String(), nullable=True, comment='Referral code used at signup'))
    op.add_column('hq_tenant', sa.Column('parent_tenant_id', sa.String(), nullable=True, comment='For multi-entity customers'))
    op.create_foreign_key('fk_hq_tenant_referred_by', 'hq_tenant', 'hq_employee', ['referred_by_agent_id'], ['id'])
    op.create_foreign_key('fk_hq_tenant_parent', 'hq_tenant', 'hq_tenant', ['parent_tenant_id'], ['id'])
    op.create_index('ix_hq_tenant_referred_by', 'hq_tenant', ['referred_by_agent_id'])

    # Add impersonation token tracking
    op.add_column('hq_tenant', sa.Column('last_impersonated_at', sa.DateTime(), nullable=True, comment='Last time HQ staff impersonated'))
    op.add_column('hq_tenant', sa.Column('last_impersonated_by_id', sa.String(), nullable=True, comment='Last HQ staff who impersonated'))
    op.create_foreign_key('fk_hq_tenant_impersonated_by', 'hq_tenant', 'hq_employee', ['last_impersonated_by_id'], ['id'])

    # ========================================================================
    # Module 3: Embedded Finance & RevOps
    # ========================================================================

    # Create banking and payroll status enums
    # Drop if exists and recreate to ensure correct values
    op.execute("""
        DO $$ BEGIN
            DROP TYPE IF EXISTS bankingstatus CASCADE;
            CREATE TYPE bankingstatus AS ENUM ('NOT_STARTED', 'KYB_PENDING', 'KYB_APPROVED', 'KYB_REJECTED', 'ACCOUNT_OPENED', 'ACCOUNT_CLOSED');
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            DROP TYPE IF EXISTS payrollstatus CASCADE;
            CREATE TYPE payrollstatus AS ENUM ('NOT_STARTED', 'ONBOARDING', 'ACTIVE', 'SUSPENDED');
        END $$;
    """)

    # Add banking and payroll tracking
    op.add_column('hq_tenant', sa.Column(
        'banking_status',
        postgresql.ENUM('NOT_STARTED', 'KYB_PENDING', 'KYB_APPROVED', 'KYB_REJECTED', 'ACCOUNT_OPENED', 'ACCOUNT_CLOSED', name='bankingstatus'),
        nullable=True,
        server_default='NOT_STARTED',
        comment='Synctera banking account status'
    ))

    op.add_column('hq_tenant', sa.Column(
        'payroll_status',
        postgresql.ENUM('NOT_STARTED', 'ONBOARDING', 'ACTIVE', 'SUSPENDED', name='payrollstatus'),
        nullable=True,
        server_default='NOT_STARTED',
        comment='CheckHQ payroll integration status'
    ))

    # Add financial metrics
    op.add_column('hq_tenant', sa.Column('mrr_amount', sa.Numeric(10, 2), nullable=True, server_default='0', comment='Monthly Recurring Revenue'))
    op.add_column('hq_tenant', sa.Column('fintech_take_rate', sa.Numeric(10, 2), nullable=True, server_default='0', comment='Estimated fintech revenue per month'))
    op.add_column('hq_tenant', sa.Column('total_deposits_mtd', sa.Numeric(12, 2), nullable=True, server_default='0', comment='Total deposits month-to-date'))
    op.add_column('hq_tenant', sa.Column('active_employees_paid', sa.Integer(), nullable=True, server_default='0', comment='Number of employees on payroll'))
    op.add_column('hq_tenant', sa.Column('lifetime_value', sa.Numeric(12, 2), nullable=True, comment='Calculated customer LTV'))
    op.add_column('hq_tenant', sa.Column('churn_risk_score', sa.Integer(), nullable=True, comment='Churn risk 0-100'))

    # Add Synctera/CheckHQ external IDs
    op.add_column('hq_tenant', sa.Column('synctera_account_id', sa.String(), nullable=True, comment='Synctera bank account ID'))
    op.add_column('hq_tenant', sa.Column('checkhq_company_id', sa.String(), nullable=True, comment='CheckHQ company ID'))
    op.create_index('ix_hq_tenant_synctera_account', 'hq_tenant', ['synctera_account_id'])
    op.create_index('ix_hq_tenant_checkhq_company', 'hq_tenant', ['checkhq_company_id'])

    # ========================================================================
    # Module 4: Affiliate & Sales Portal
    # ========================================================================

    # Add referral tracking to hq_employee
    op.add_column('hq_employee', sa.Column('referral_code', sa.String(length=50), nullable=True, unique=True, comment='Unique referral code for affiliates'))
    op.add_column('hq_employee', sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True, server_default='10', comment='Commission percentage (0-100)'))
    op.add_column('hq_employee', sa.Column('is_affiliate', sa.Boolean(), nullable=True, server_default='false', comment='Is this employee an affiliate/agent?'))
    op.add_column('hq_employee', sa.Column('total_referrals', sa.Integer(), nullable=True, server_default='0', comment='Total successful referrals'))
    op.add_column('hq_employee', sa.Column('total_commission_earned', sa.Numeric(12, 2), nullable=True, server_default='0', comment='Lifetime commission earned'))
    op.create_index('ix_hq_employee_referral_code', 'hq_employee', ['referral_code'], unique=True)
    op.create_index('ix_hq_employee_is_affiliate', 'hq_employee', ['is_affiliate'])

    # Create commission_payout table
    op.create_table(
        'hq_commission_payout',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('agent_id', sa.String(), sa.ForeignKey('hq_employee.id'), nullable=False, index=True, comment='Sales agent receiving commission'),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('hq_tenant.id'), nullable=False, index=True, comment='Tenant that generated commission'),
        sa.Column('period_start', sa.DateTime(), nullable=False, comment='Commission period start'),
        sa.Column('period_end', sa.DateTime(), nullable=False, comment='Commission period end'),
        sa.Column('base_amount', sa.Numeric(12, 2), nullable=False, comment='Base amount before commission'),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=False, comment='Commission rate applied'),
        sa.Column('commission_amount', sa.Numeric(12, 2), nullable=False, comment='Calculated commission'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending', comment='Status: pending, approved, paid, cancelled'),
        sa.Column('paid_at', sa.DateTime(), nullable=True, comment='When commission was paid'),
        sa.Column('payment_method', sa.String(length=100), nullable=True, comment='How commission was paid'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
    )
    op.create_index('ix_commission_payout_status', 'hq_commission_payout', ['status'])
    op.create_index('ix_commission_payout_period', 'hq_commission_payout', ['period_start', 'period_end'])

    # ========================================================================
    # Module 5: AI Orchestration & Cost Monitoring
    # ========================================================================

    # Create ai_usage_log table
    op.create_table(
        'hq_ai_usage_log',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('hq_tenant.id'), nullable=True, index=True, comment='Tenant using AI (null for HQ usage)'),
        sa.Column('user_id', sa.String(), nullable=True, comment='Specific user if tracked'),
        sa.Column('model_name', sa.String(length=100), nullable=False, index=True, comment='e.g., llama-4-maverick, llama-4-scout'),
        sa.Column('feature', sa.String(length=100), nullable=False, index=True, comment='Feature using AI: dispatch, email, compliance, etc'),
        sa.Column('input_tokens', sa.Integer(), nullable=False, comment='Input tokens consumed'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, comment='Output tokens generated'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, comment='Total tokens (input + output)'),
        sa.Column('latency_ms', sa.Integer(), nullable=True, comment='Response latency in milliseconds'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=True, comment='Estimated cost in USD'),
        sa.Column('suggestion_accepted', sa.Boolean(), nullable=True, comment='Did user accept the AI suggestion?'),
        sa.Column('error', sa.Text(), nullable=True, comment='Error message if failed'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, comment='Additional context'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True)
    )
    op.create_index('ix_ai_usage_tenant_date', 'hq_ai_usage_log', ['tenant_id', 'created_at'])
    op.create_index('ix_ai_usage_model_date', 'hq_ai_usage_log', ['model_name', 'created_at'])
    op.create_index('ix_ai_usage_feature', 'hq_ai_usage_log', ['feature'])

    # Create ai_anomaly_alert table
    op.create_table(
        'hq_ai_anomaly_alert',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('hq_tenant.id'), nullable=True, index=True),
        sa.Column('alert_type', sa.String(length=100), nullable=False, comment='Type: SPIKE, ABUSE, LOW_ACCEPTANCE, HIGH_ERROR'),
        sa.Column('severity', sa.String(length=50), nullable=False, comment='Severity: info, warning, critical'),
        sa.Column('metric', sa.String(length=100), nullable=False, comment='Metric that triggered alert'),
        sa.Column('threshold', sa.Numeric(12, 2), nullable=False, comment='Threshold value'),
        sa.Column('actual_value', sa.Numeric(12, 2), nullable=False, comment='Actual value that triggered'),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open', comment='Status: open, acknowledged, resolved, false_positive'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.String(), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True)
    )
    op.create_index('ix_ai_anomaly_status', 'hq_ai_anomaly_alert', ['status'])
    op.create_index('ix_ai_anomaly_severity', 'hq_ai_anomaly_alert', ['severity'])

    # ========================================================================
    # Additional Enterprise Features
    # ========================================================================

    # Create webhook_log table for tracking all incoming webhooks
    op.create_table(
        'hq_webhook_log',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('provider', sa.String(length=100), nullable=False, index=True, comment='Provider: stripe, synctera, checkhq'),
        sa.Column('event_type', sa.String(length=200), nullable=False, index=True, comment='Event type from webhook'),
        sa.Column('webhook_id', sa.String(length=200), nullable=True, comment='External webhook ID for idempotency'),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('hq_tenant.id'), nullable=True, index=True),
        sa.Column('payload', postgresql.JSONB(), nullable=False, comment='Full webhook payload'),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false', comment='Was this webhook processed?'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True, comment='Processing error if any'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True)
    )
    op.create_index('ix_webhook_provider_event', 'hq_webhook_log', ['provider', 'event_type'])
    op.create_index('ix_webhook_processed', 'hq_webhook_log', ['processed'])
    op.create_unique_constraint('uq_webhook_provider_id', 'hq_webhook_log', ['provider', 'webhook_id'])

    # Create impersonation_log table for security/audit
    op.create_table(
        'hq_impersonation_log',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('hq_employee_id', sa.String(), sa.ForeignKey('hq_employee.id'), nullable=False, index=True, comment='HQ staff who impersonated'),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('hq_tenant.id'), nullable=False, index=True, comment='Tenant impersonated'),
        sa.Column('reason', sa.Text(), nullable=False, comment='Reason for impersonation'),
        sa.Column('session_token', sa.String(), nullable=False, comment='Generated impersonation token'),
        sa.Column('expires_at', sa.DateTime(), nullable=False, comment='Token expiration'),
        sa.Column('ended_at', sa.DateTime(), nullable=True, comment='When impersonation ended'),
        sa.Column('actions_taken', postgresql.JSONB(), nullable=True, comment='Log of actions performed'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True)
    )
    op.create_index('ix_impersonation_employee', 'hq_impersonation_log', ['hq_employee_id'])
    op.create_index('ix_impersonation_tenant', 'hq_impersonation_log', ['tenant_id'])


def downgrade() -> None:
    # Drop new tables
    op.drop_table('hq_impersonation_log')
    op.drop_table('hq_webhook_log')
    op.drop_table('hq_ai_anomaly_alert')
    op.drop_table('hq_ai_usage_log')
    op.drop_table('hq_commission_payout')

    # Drop hq_employee columns
    op.drop_index('ix_hq_employee_is_affiliate', 'hq_employee')
    op.drop_index('ix_hq_employee_referral_code', 'hq_employee')
    op.drop_column('hq_employee', 'total_commission_earned')
    op.drop_column('hq_employee', 'total_referrals')
    op.drop_column('hq_employee', 'is_affiliate')
    op.drop_column('hq_employee', 'commission_rate')
    op.drop_column('hq_employee', 'referral_code')

    # Drop hq_tenant finance columns
    op.drop_index('ix_hq_tenant_checkhq_company', 'hq_tenant')
    op.drop_index('ix_hq_tenant_synctera_account', 'hq_tenant')
    op.drop_column('hq_tenant', 'checkhq_company_id')
    op.drop_column('hq_tenant', 'synctera_account_id')
    op.drop_column('hq_tenant', 'churn_risk_score')
    op.drop_column('hq_tenant', 'lifetime_value')
    op.drop_column('hq_tenant', 'active_employees_paid')
    op.drop_column('hq_tenant', 'total_deposits_mtd')
    op.drop_column('hq_tenant', 'fintech_take_rate')
    op.drop_column('hq_tenant', 'mrr_amount')
    op.drop_column('hq_tenant', 'payroll_status')
    op.drop_column('hq_tenant', 'banking_status')

    # Drop hq_tenant management columns
    op.drop_constraint('fk_hq_tenant_impersonated_by', 'hq_tenant')
    op.drop_column('hq_tenant', 'last_impersonated_by_id')
    op.drop_column('hq_tenant', 'last_impersonated_at')
    op.drop_index('ix_hq_tenant_referred_by', 'hq_tenant')
    op.drop_constraint('fk_hq_tenant_parent', 'hq_tenant')
    op.drop_constraint('fk_hq_tenant_referred_by', 'hq_tenant')
    op.drop_column('hq_tenant', 'parent_tenant_id')
    op.drop_column('hq_tenant', 'referral_code_used')
    op.drop_column('hq_tenant', 'referred_by_agent_id')
    op.drop_constraint('fk_hq_tenant_paused_by', 'hq_tenant')
    op.drop_column('hq_tenant', 'paused_by_id')
    op.drop_column('hq_tenant', 'pause_expires_at')
    op.drop_column('hq_tenant', 'pause_reason')
    op.drop_column('hq_tenant', 'paused_at')
    op.drop_column('hq_tenant', 'subscription_status')

    # Drop hq_deal columns
    op.drop_column('hq_deal', 'time_to_first_contact_hours')
    op.drop_column('hq_deal', 'first_contact_at')
    op.drop_index('ix_hq_deal_claimed_by', 'hq_deal')
    op.drop_index('ix_hq_deal_enrichment_status', 'hq_deal')
    op.drop_index('ix_hq_deal_pql_score', 'hq_deal')
    op.drop_constraint('fk_hq_deal_claimed_by', 'hq_deal')
    op.drop_column('hq_deal', 'claim_expires_at')
    op.drop_column('hq_deal', 'claimed_at')
    op.drop_column('hq_deal', 'claimed_by_id')
    op.drop_column('hq_deal', 'enrichment_attempts')
    op.drop_column('hq_deal', 'enriched_at')
    op.drop_column('hq_deal', 'enrichment_status')
    op.drop_column('hq_deal', 'pql_score')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS payrollstatus')
    op.execute('DROP TYPE IF EXISTS bankingstatus')
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')
