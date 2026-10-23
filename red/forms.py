import os

from django import forms

from .models import Profesional

EXTENSIONES = {".pdf", ".jpg", ".jpeg", ".png"}
TAMANO_MAXIMO = 5 * 1024 * 1024


def _validar_archivo(archivo, etiqueta):
    if not archivo:
        raise forms.ValidationError(f"Falta la {etiqueta}.")
    ext = os.path.splitext(archivo.name)[1].lower()
    if ext not in EXTENSIONES:
        raise forms.ValidationError("Solo PDF, JPG o PNG.")
    if archivo.size > TAMANO_MAXIMO:
        raise forms.ValidationError("El archivo supera los 5 MB.")


class PostulacionForm(forms.ModelForm):
    constancia_matricula = forms.FileField(
        label="Constancia de matrícula",
        error_messages={"required": "Falta la constancia de matrícula."},
        help_text="PDF o foto de la constancia vigente emitida por el colegio o el registro provincial.")
    seguro = forms.FileField(
        label="Seguro de responsabilidad civil",
        error_messages={"required": "Falta la póliza de seguro."},
        help_text="Póliza vigente. PDF o foto de la primera página.")
    identidad = forms.FileField(
        label="Documento de identidad",
        help_text="Frente del DNI. Se usa solo para verificar identidad y no se publica.",
        required=False)

    class Meta:
        model = Profesional
        fields = ["nombre", "apellido", "email", "telefono", "matricula", "provincia", "registro",
                  "titulo", "universidad", "anio_egreso", "especialidades", "enfoque",
                  "modalidad", "ciudad", "bio", "acepta_protocolo", "consentimiento_datos",
                  "acepta_sin_comision"]
        labels = {
            "acepta_protocolo": "Acepto el protocolo de derivación de Onto",
            "consentimiento_datos": "Consiento el tratamiento de mis datos para la verificación",
            "acepta_sin_comision": "Entiendo que la red no paga ni cobra comisiones por derivación",
        }
        widgets = {
            "enfoque": forms.Textarea(attrs={"rows": 4}),
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_matricula(self):
        matricula = " ".join((self.cleaned_data.get("matricula") or "").split()).upper()
        if len(matricula) < 4:
            raise forms.ValidationError("Escriba la matrícula completa.")
        if not any(c.isdigit() for c in matricula):
            raise forms.ValidationError("La matrícula debería incluir números. Revísela.")
        return matricula

    def clean_constancia_matricula(self):
        archivo = self.cleaned_data.get("constancia_matricula")
        _validar_archivo(archivo, "constancia de matrícula")
        return archivo

    def clean_seguro(self):
        archivo = self.cleaned_data.get("seguro")
        _validar_archivo(archivo, "póliza de seguro")
        return archivo

    def clean_identidad(self):
        archivo = self.cleaned_data.get("identidad")
        if archivo:
            _validar_archivo(archivo, "foto del DNI")
        return archivo

    def clean(self):
        datos = super().clean()
        if not datos.get("acepta_protocolo"):
            self.add_error("acepta_protocolo", "Debe aceptar el protocolo de derivación.")
        if not datos.get("consentimiento_datos"):
            self.add_error("consentimiento_datos", "Necesitamos su consentimiento para tratar los datos.")
        if not datos.get("acepta_sin_comision"):
            self.add_error("acepta_sin_comision",
                           "La red funciona sin pagos ni comisiones por derivación.")
        return datos
