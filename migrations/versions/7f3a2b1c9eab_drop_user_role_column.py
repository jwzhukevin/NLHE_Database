"""drop user.role column

Revision ID: 7f3a2b1c9eab
Revises: 362aca3e4678
Create Date: 2025-10-02 15:19:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7f3a2b1c9eab'
down_revision = '362aca3e4678'
branch_labels = None
depends_on = None


def upgrade():
    # 安全删除 user.role 列（批处理模式，兼容不同数据库）
    with op.batch_alter_table('user', schema=None) as batch_op:
        # 若目标环境不存在该列，drop_column 可能抛错；
        # 一般情况下按照模型演进应当存在该列，若已手动删除可忽略异常。
        batch_op.drop_column('role')


def downgrade():
    # 回滚时恢复 user.role 列，默认值为 'user'，以兼容旧代码路径
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('role', sa.String(length=10), server_default='user', nullable=True)
        )
