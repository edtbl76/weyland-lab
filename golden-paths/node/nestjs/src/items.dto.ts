// C2 the typed models: class-validator rules, bound by the global ValidationPipe (transform: true), and described
// for the OpenAPI document (C10) by @ApiProperty.
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { ArrayMaxSize, IsArray, IsInt, IsOptional, IsString, Length, Max, Min } from 'class-validator';

export class CreateItemDto {
  @ApiProperty({ minLength: 1, maxLength: 64 })
  @IsString()
  @Length(1, 64)
  name!: string;

  @ApiPropertyOptional({ type: [String], maxItems: 5, default: [] })
  @IsOptional()
  @IsArray()
  @ArrayMaxSize(5)
  @IsString({ each: true })
  tags: string[] = [];
}

export class ItemDto extends CreateItemDto {
  @ApiProperty()
  id!: number;
}

export class ListQueryDto {
  @ApiPropertyOptional({ minimum: 1, maximum: 100, default: 20 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit: number = 20;

  @ApiPropertyOptional({ minimum: 0, default: 0 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(0)
  offset: number = 0;
}

export class ItemPageDto {
  @ApiProperty({ type: [ItemDto] })
  items!: ItemDto[];

  @ApiProperty()
  limit!: number;

  @ApiProperty()
  offset!: number;
}

export class IdParamDto {
  @ApiProperty({ minimum: 1 })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  id!: number;
}
