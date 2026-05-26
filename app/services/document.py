"""
app/services/document.py

Генерация документов (КП, Счёт, Договор, Акт) и загрузка в S3.
Использует ReportLab для PDF.
"""
from __future__ import annotations

import io
import uuid
import logging
from datetime import date
from typing import Optional

import aioboto3
from botocore.config import Config
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class StorageService:
    """Загрузка файлов в S3-совместимое хранилище (Yandex Cloud)."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "ru-central1",
    ):
        self.endpoint = endpoint
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        public: bool = True,
    ) -> str:
        """Загружает байты в S3, возвращает публичный URL."""
        session = aioboto3.Session(
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
        )
        async with session.client(
            "s3",
            endpoint_url=self.endpoint,
            config=Config(signature_version="s3v4"),
        ) as s3:
            extra = {}
            if public:
                extra["ACL"] = "public-read"

            await s3.put_object(
                Bucket=self.bucket,
                Key=filename,
                Body=data,
                ContentType=content_type,
                **extra,
            )

        return f"{self.endpoint}/{self.bucket}/{filename}"


class DocumentService:
    """Генерирует PDF-документы и сохраняет их через StorageService."""

    def __init__(self, storage: StorageService):
        self.storage = storage

    # ── Коммерческое предложение ─────────────────────────────────────────

    async def create_commercial(
        self,
        client_name: str,
        client_phone: str,
        service_name: str,
        service_description: str,
        amount: float,
        manager_name: str,
        deal_id: int,
    ) -> str:
        """Генерирует КП в PDF и загружает в S3. Возвращает URL."""
        pdf_bytes = self._build_commercial_pdf(
            client_name=client_name,
            client_phone=client_phone,
            service_name=service_name,
            service_description=service_description,
            amount=amount,
            manager_name=manager_name,
        )
        filename = f"documents/kp_{deal_id}_{uuid.uuid4().hex[:8]}.pdf"
        url = await self.storage.upload_bytes(
            data=pdf_bytes,
            filename=filename,
            content_type="application/pdf",
        )
        logger.info("Commercial PDF uploaded: %s", url)
        return url

    # ── Счёт на оплату ───────────────────────────────────────────────────

    async def create_invoice(
        self,
        client_name: str,
        service_name: str,
        amount: float,
        deal_id: int,
        invoice_number: Optional[str] = None,
    ) -> str:
        if invoice_number is None:
            invoice_number = f"БХ-{date.today().year}-{deal_id:04d}"

        pdf_bytes = self._build_invoice_pdf(
            client_name=client_name,
            service_name=service_name,
            amount=amount,
            invoice_number=invoice_number,
        )
        filename = f"documents/invoice_{deal_id}_{uuid.uuid4().hex[:8]}.pdf"
        url = await self.storage.upload_bytes(
            data=pdf_bytes,
            filename=filename,
            content_type="application/pdf",
        )
        return url

    # ── PDF-генерация КП ─────────────────────────────────────────────────

    def _build_commercial_pdf(
        self,
        client_name: str,
        client_phone: str,
        service_name: str,
        service_description: str,
        amount: float,
        manager_name: str,
    ) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=20,
            spaceAfter=0.5 * cm,
            textColor=colors.HexColor("#1a1a2e"),
            alignment=1,  # Center
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            spaceAfter=0.3 * cm,
        )
        label_style = ParagraphStyle(
            "Label",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#666666"),
        )

        elements = []

        # Заголовок
        elements.append(Paragraph("АГЕНТСТВО «БЕРХАЯТ»", title_style))
        elements.append(Paragraph("Коммерческое предложение", styles["Heading2"]))
        elements.append(Spacer(1, 0.5 * cm))

        # Дата
        elements.append(
            Paragraph(f"Дата: {date.today().strftime('%d.%m.%Y')}", label_style)
        )
        elements.append(Spacer(1, 0.3 * cm))

        # Кому
        elements.append(Paragraph(f"<b>Уважаемый(ая) {client_name}!</b>", body_style))
        elements.append(
            Paragraph(
                "Агентство <b>БЕРХАЯТ</b> предлагает вам следующее решение:",
                body_style,
            )
        )
        elements.append(Spacer(1, 0.5 * cm))

        # Таблица услуги
        data = [
            ["Услуга", "Описание", "Стоимость"],
            [service_name, service_description[:120], f"{amount:,.0f} ₸"],
        ]
        table = Table(data, colWidths=[5 * cm, 8 * cm, 4 * cm])
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ])
        )
        elements.append(table)
        elements.append(Spacer(1, 0.5 * cm))

        # Итого
        total_table = Table(
            [["", "ИТОГО:", f"{amount:,.0f} ₸"]],
            colWidths=[5 * cm, 8 * cm, 4 * cm],
        )
        total_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#1a1a2e")),
        ]))
        elements.append(total_table)
        elements.append(Spacer(1, 1 * cm))

        # Подпись
        elements.append(
            Paragraph(
                f"С уважением,<br/><b>{manager_name}</b><br/>"
                f"Менеджер агентства БЕРХАЯТ<br/>"
                f"Тел: +7 (___) ___-__-__",
                body_style,
            )
        )

        doc.build(elements)
        return buf.getvalue()

    # ── PDF-генерация счёта ──────────────────────────────────────────────

    def _build_invoice_pdf(
        self,
        client_name: str,
        service_name: str,
        amount: float,
        invoice_number: str,
    ) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)

        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"СЧЁТ НА ОПЛАТУ № {invoice_number}", styles["Heading1"]))
        elements.append(Paragraph(f"от {date.today().strftime('%d.%m.%Y')}", styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(f"<b>Плательщик:</b> {client_name}", styles["Normal"]))
        elements.append(Paragraph("<b>Исполнитель:</b> Агентство БЕРХАЯТ", styles["Normal"]))
        elements.append(Spacer(1, 0.5 * cm))

        data = [
            ["№", "Наименование", "Кол-во", "Ед.", "Сумма"],
            ["1", service_name, "1", "усл.", f"{amount:,.0f} ₸"],
            ["", "", "", "ИТОГО:", f"{amount:,.0f} ₸"],
        ]
        table = Table(data, colWidths=[1*cm, 9*cm, 2*cm, 2*cm, 4*cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
            ("FONTNAME", (3, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 1 * cm))
        elements.append(Paragraph("Подпись: ____________________", styles["Normal"]))
        elements.append(Paragraph("Агентство БЕРХАЯТ", styles["Normal"]))

        doc.build(elements)
        return buf.getvalue()
