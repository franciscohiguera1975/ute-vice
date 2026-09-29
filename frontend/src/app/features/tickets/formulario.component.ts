import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule, type AbstractControl } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { EMPTY, Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { CatalogosStore } from '@core/catalogos.store';
import { NotificacionesService } from '@core/notificaciones.service';
import {
  TipoCatalogo,
  type DatosPersona,
  type ErrorApi,
  type Persona,
} from '@domain/modelos';
import { RepositorioPersonas, RepositorioTickets } from '@domain/puertos';

import { validadorCedula } from '../personas/validador-cedula';

/** Fecha de hoy en formato `yyyy-MM-dd`, el que espera un `<input type="date">`. */
const hoyISO = (): string => new Date().toISOString().slice(0, 10);

@Component({
  selector: 'ute-formulario-ticket',
  standalone: true,
  imports: [FormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './formulario.component.html',
  styleUrl: './formulario.component.scss',
})
export class FormularioTicketComponent {
  private readonly tickets = inject(RepositorioTickets);
  private readonly personas = inject(RepositorioPersonas);
  private readonly notificaciones = inject(NotificacionesService);
  private readonly router = inject(Router);
  protected readonly catalogos = inject(CatalogosStore);

  protected readonly TipoCatalogo = TipoCatalogo;

  // --- Solicitante ---
  protected readonly busquedaPersona = signal('');
  protected readonly resultadosPersona = signal<readonly Persona[]>([]);
  protected readonly buscandoPersona = signal(false);
  protected readonly solicitante = signal<Persona | null>(null);
  private readonly busquedaPersona$ = new Subject<string>();

  // --- Alta rapida de persona ---
  protected readonly mostrarModalPersona = signal(false);
  protected readonly nuevaCedula = signal('');
  protected readonly nuevosNombres = signal('');
  protected readonly nuevosApellidos = signal('');
  protected readonly nuevaFacultadId = signal('');
  protected readonly nuevaCarreraId = signal('');
  protected readonly nuevoTelefono = signal('');
  protected readonly nuevoEmailInstitucional = signal('');
  protected readonly nuevoEmailPersonal = signal('');
  protected readonly creandoPersona = signal(false);

  // --- Ticket ---
  protected readonly titulo = signal('');
  protected readonly descripcion = signal('');
  /** Cuando se pidio el soporte. Nace en hoy, pero es editable desde el formulario. */
  protected readonly fechaSolicitud = signal(hoyISO());
  protected readonly hoy = hoyISO();
  protected readonly enviando = signal(false);

  constructor() {
    this.catalogos.cargar();

    this.busquedaPersona$
      .pipe(
        debounceTime(320),
        distinctUntilChanged(),
        switchMap((texto) => {
          if (!texto) return EMPTY;
          this.buscandoPersona.set(true);
          return this.personas.listar({ texto }, { pagina: 1, tamano: 8 });
        }),
        takeUntilDestroyed(),
      )
      .subscribe({
        next: (pagina) => {
          this.buscandoPersona.set(false);
          this.resultadosPersona.set(pagina.items);
        },
        error: () => this.buscandoPersona.set(false),
      });
  }

  protected buscarPersona(valor: string): void {
    this.busquedaPersona.set(valor);
    if (!valor.trim()) {
      this.resultadosPersona.set([]);
      return;
    }
    this.busquedaPersona$.next(valor.trim());
  }

  protected seleccionarPersona(persona: Persona): void {
    this.solicitante.set(persona);
    this.resultadosPersona.set([]);
    this.busquedaPersona.set('');
  }

  protected quitarSolicitante(): void {
    this.solicitante.set(null);
  }

  // ------------------------------------------------------- alta rapida
  protected abrirModalPersona(): void {
    this.nuevaCedula.set('');
    this.nuevosNombres.set(this.busquedaPersona());
    this.nuevosApellidos.set('');
    this.nuevaFacultadId.set('');
    this.nuevaCarreraId.set('');
    this.nuevoTelefono.set('');
    this.nuevoEmailInstitucional.set('');
    this.nuevoEmailPersonal.set('');
    this.mostrarModalPersona.set(true);
  }

  protected crearPersona(): void {
    const cedula = this.nuevaCedula().trim();
    const nombres = this.nuevosNombres().trim();
    const apellidos = this.nuevosApellidos().trim();

    if (!nombres || !apellidos) {
      this.notificaciones.aviso('Ingrese nombres y apellidos');
      return;
    }
    if (validadorCedula({ value: cedula } as AbstractControl)) {
      this.notificaciones.aviso('La cedula ingresada no es valida');
      return;
    }

    const facultad = this.catalogos.nombreDe(TipoCatalogo.FACULTAD, this.nuevaFacultadId());
    const carrera = this.catalogos.nombreDe(TipoCatalogo.CARRERA, this.nuevaCarreraId());
    const unidad = [facultad, carrera].filter(Boolean).join(' — ') || null;

    const datos: DatosPersona = {
      cedula,
      nombres,
      apellidos,
      telefono: this.nuevoTelefono().trim() || null,
      emailInstitucional: this.nuevoEmailInstitucional().trim() || null,
      emailPersonal: this.nuevoEmailPersonal().trim() || null,
      unidad,
      facultadId: this.nuevaFacultadId() || null,
      carreraId: this.nuevaCarreraId() || null,
    };

    this.creandoPersona.set(true);
    this.personas.crear(datos).subscribe({
      next: (persona) => {
        this.creandoPersona.set(false);
        this.mostrarModalPersona.set(false);
        this.seleccionarPersona(persona);
        this.notificaciones.exito('Persona registrada');
      },
      error: (error: ErrorApi) => {
        this.creandoPersona.set(false);
        this.notificaciones.error('No fue posible registrar la persona', error.mensaje);
      },
    });
  }

  // ------------------------------------------------------------- ticket
  protected enviar(): void {
    const solicitante = this.solicitante();
    if (!solicitante) {
      this.notificaciones.aviso('Seleccione o registre al solicitante');
      return;
    }
    if (!this.titulo().trim() || !this.descripcion().trim()) {
      this.notificaciones.aviso('Complete el titulo y la descripcion');
      return;
    }

    this.enviando.set(true);
    this.tickets
      .crear({
        titulo: this.titulo().trim(),
        descripcion: this.descripcion().trim(),
        solicitanteId: solicitante.id,
        fechaSolicitud: this.fechaSolicitud(),
      })
      .subscribe({
        next: (ticket) => {
          this.notificaciones.exito('Ticket registrado');
          void this.router.navigate(['/tickets', ticket.id]);
        },
        error: (error: ErrorApi) => {
          this.enviando.set(false);
          this.notificaciones.error('No fue posible registrar el ticket', error.mensaje);
        },
      });
  }
}
