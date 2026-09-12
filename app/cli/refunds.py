import click
from flask.cli import AppGroup

from app.models import RefundStatus
from app.services.refund import (
    RefundError,
    list_processing_vnpay_refunds,
    process_overdue_funding_refunds,
    process_pending_momo_refunds,
    process_pending_vnpay_refunds,
    reconcile_vnpay_refund_manually,
)


refunds_cli = AppGroup(
    "refunds",
    help="Xử lý định kỳ chính sách hoàn tiền.",
)


@refunds_cli.command("funding-expire")
def funding_expire() -> None:
    """Refund split bookings that missed their 12-hour funding deadline."""
    processed_count = process_overdue_funding_refunds()
    click.echo(f"Đã xử lý hoàn tiền cho {processed_count} booking thiếu tiền.")


@refunds_cli.command("momo-pending")
def momo_pending() -> None:
    """Submit or query durable MoMo Sandbox refund records."""
    succeeded_count = process_pending_momo_refunds()
    click.echo(f"Đã hoàn tất {succeeded_count} yêu cầu hoàn tiền MoMo.")


@refunds_cli.command("vnpay-pending")
def vnpay_pending() -> None:
    """Submit durable VNPAY Sandbox refund records still PENDING/PROCESSING."""
    succeeded_count = process_pending_vnpay_refunds()
    click.echo(f"Đã hoàn tất {succeeded_count} yêu cầu hoàn tiền VNPAY.")


@refunds_cli.command("vnpay-processing")
def vnpay_processing() -> None:
    """List durable VNPAY refunds stuck at PROCESSING (read-only).

    VNPAY has no API to safely identify a specific refund's outcome (see
    reconcile_vnpay_refund_manually's docstring), so these must be checked
    by hand against the VNPAY Sandbox merchant portal before running
    `flask refunds vnpay-reconcile`.
    """
    refunds = list_processing_vnpay_refunds()
    if not refunds:
        click.echo("Không có yêu cầu hoàn tiền VNPAY nào đang PROCESSING.")
        return
    for refund in refunds:
        click.echo(
            f"Refund #{refund.id} | order_id={refund.order_id} | "
            f"request_id={refund.request_id} | amount={refund.amount} | "
            f"result_code={refund.result_code} | "
            f"provider_refund_trans_id={refund.provider_refund_trans_id} | "
            f"payment_order_id={refund.payment.order_id} | "
            f"payment_provider_trans_id={refund.payment.provider_trans_id}"
        )


@refunds_cli.command("vnpay-reconcile")
@click.argument("refund_id", type=int)
@click.argument("outcome", type=click.Choice(["success", "failed"]))
@click.option(
    "--provider-trans-id",
    default=None,
    help=(
        "Mã giao dịch hoàn tiền thực tế lấy từ cổng merchant VNPAY "
        "(bắt buộc khi outcome=success)."
    ),
)
@click.option(
    "--result-code",
    default=None,
    help=(
        "Mã kết quả VNPAY thực tế đã xác minh "
        "(mặc định 00 khi success, MANUAL_REJECTED khi failed)."
    ),
)
def vnpay_reconcile(
    refund_id: int,
    outcome: str,
    provider_trans_id: str | None,
    result_code: str | None,
) -> None:
    """Manually record a PROCESSING VNPAY refund's real, verified outcome.

    Only use this after personally checking the transaction against the
    VNPAY Sandbox merchant portal (or SIT data) — this project never
    auto-promotes a refund from PROCESSING because VNPAY's queryDr API
    cannot safely identify a specific refund transaction.
    """
    status = (
        RefundStatus.SUCCESS.value if outcome == "success" else RefundStatus.FAILED.value
    )
    try:
        refund = reconcile_vnpay_refund_manually(
            refund_id,
            outcome=status,
            provider_trans_id=provider_trans_id,
            result_code=result_code,
        )
    except RefundError as exc:
        click.echo(f"Không thể đối soát: {exc}")
        return
    click.echo(f"Đã ghi nhận Refund #{refund.id} là {refund.status}.")
