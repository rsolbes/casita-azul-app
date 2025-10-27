import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { AgentService, Agent } from '../../services/agent.service'; // Use AgentService
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-manage-agents',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterLink],
  templateUrl: './manage-agents.component.html',
  styleUrls: ['./manage-agents.component.css'] // You'll create this CSS file
})
export class ManageAgentsComponent implements OnInit {
  agents: Agent[] = [];
  isLoading = false;
  errorMessage = '';
  successMessage = '';

  showAddEditForm = false;
  isEditMode = false;
  agentForm: FormGroup;
  editingAgentId: number | null = null;

  constructor(
    private agentService: AgentService, // Inject AgentService
    private fb: FormBuilder
  ) {
    this.agentForm = this.fb.group({
      nombre: ['', Validators.required],
      email: ['', [Validators.required, Validators.email]],
      telefono: [''] // Optional
    });
  }

  ngOnInit(): void {
    this.loadAgents();
  }

  loadAgents(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.agentService.getAgents().subscribe({
      next: (agents) => {
        this.agents = agents;
        this.isLoading = false;
      },
      error: (err) => {
        this.errorMessage = `Error cargando agentes: ${err.error?.error || err.message}`;
        console.error(err);
        this.isLoading = false;
      }
    });
  }

  openAddForm(): void {
    this.isEditMode = false;
    this.showAddEditForm = true;
    this.editingAgentId = null;
    this.agentForm.reset();
    this.errorMessage = '';
    this.successMessage = '';
  }

  openEditForm(agent: Agent): void {
     if (!agent.id) return; // Should have ID if editing
    this.isEditMode = true;
    this.showAddEditForm = true;
    this.editingAgentId = agent.id;
    this.agentForm.patchValue(agent); // Populate form
    this.errorMessage = '';
    this.successMessage = '';
  }

  cancelForm(): void {
    this.showAddEditForm = false;
    this.isEditMode = false;
    this.editingAgentId = null;
    this.agentForm.reset();
  }

  onSubmitAgent(): void {
    if (this.agentForm.invalid) {
      this.errorMessage = 'Por favor, completa el formulario correctamente.';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';
    this.successMessage = '';

    const agentData: Agent = this.agentForm.value;

    if (this.isEditMode && this.editingAgentId !== null) {
      // --- Update Agent ---
      this.agentService.updateAgent(this.editingAgentId, agentData).subscribe({
        next: () => {
          this.successMessage = `Agente ${agentData.nombre} actualizado exitosamente.`;
          this.isLoading = false;
          this.cancelForm();
          this.loadAgents(); // Reload list
        },
        error: (err) => {
          this.errorMessage = `Error actualizando agente: ${err.error?.error || err.message}`;
          console.error(err);
          this.isLoading = false;
        }
      });
    } else {
      // --- Create Agent ---
      this.agentService.createAgent(agentData).subscribe({
        next: (response) => {
          this.successMessage = `Agente ${agentData.nombre} creado exitosamente (ID: ${response.id}).`;
          this.isLoading = false;
          this.cancelForm();
          this.loadAgents(); // Reload list
        },
        error: (err) => {
          this.errorMessage = `Error creando agente: ${err.error?.error || err.message}`;
          console.error(err);
          this.isLoading = false;
        }
      });
    }
  }

  deleteAgent(agentId: number | undefined, agentName: string): void {
     if (!agentId) return;
    if (confirm(`¿Estás seguro de eliminar al agente ${agentName}?`)) {
      this.isLoading = true;
      this.errorMessage = '';
      this.successMessage = '';
      this.agentService.deleteAgent(agentId).subscribe({
        next: () => {
          this.successMessage = `Agente ${agentName} eliminado.`;
          this.isLoading = false;
          this.agents = this.agents.filter(a => a.id !== agentId); // Update UI
          // Optionally reload: this.loadAgents();
        },
        error: (err) => {
          this.errorMessage = `Error eliminando agente: ${err.error?.error || err.message}`;
          console.error(err);
          this.isLoading = false;
        }
      });
    }
  }
}